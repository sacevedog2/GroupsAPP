from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db import models
from app.schemas import groups as schemas
from app.core.events import publisher
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[schemas.GroupResponse])
def list_groups(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    groups = (
        db.query(models.Group)
        .join(models.GroupMember, models.GroupMember.group_id == models.Group.id)
        .filter(models.GroupMember.user_id == current_user_id)
        .order_by(models.Group.created_at.desc())
        .all()
    )
    return groups

@router.post("/", response_model=schemas.GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(group: schemas.GroupCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    member_ids = []
    for user_id in group.member_ids:
        normalized_user_id = user_id.strip().lower()
        if normalized_user_id and normalized_user_id != current_user_id and normalized_user_id not in member_ids:
            member_ids.append(normalized_user_id)

    if len(member_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="Para crear un grupo debes agregar al menos otros 2 usuarios.",
        )

    db_group = models.Group(
        name=group.name,
        description=group.description,
        settings=group.settings
    )
    db.add(db_group)
    db.flush() # To get the db_group.id

    # Creator becomes admin
    db_member = models.GroupMember(
        group_id=db_group.id,
        user_id=current_user_id,
        role=models.RoleEnum.ADMIN.value
    )
    db.add(db_member)
    for user_id in member_ids:
        db.add(
            models.GroupMember(
                group_id=db_group.id,
                user_id=user_id,
                role=models.RoleEnum.MEMBER.value,
            )
        )
    db.commit()
    db.refresh(db_group)
    
    publisher.publish("group.created", {
        "group_id": db_group.id,
        "name": db_group.name,
        "creator_id": current_user_id,
        "member_ids": member_ids
    })
    for user_id in member_ids:
        publisher.publish("member.added", {
            "group_id": db_group.id,
            "user_id": user_id,
            "role": models.RoleEnum.MEMBER.value,
            "actor_user_id": current_user_id
        })
    return db_group

@router.get("/{group_id}", response_model=schemas.GroupDetailResponse)
def get_group(group_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@router.post("/{group_id}/members", response_model=schemas.GroupMemberResponse)
def add_member(group_id: str, member: schemas.GroupMemberCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
        
    db_member = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == member.user_id
    ).first()
    if db_member:
        raise HTTPException(status_code=400, detail="User is already a member")

    new_member = models.GroupMember(
        group_id=group_id,
        user_id=member.user_id,
        role=member.role
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    
    publisher.publish("member.added", {
        "group_id": new_member.group_id,
        "user_id": new_member.user_id,
        "role": new_member.role,
        "actor_user_id": current_user_id
    })
    return new_member

@router.get("/{group_id}/members", response_model=List[schemas.GroupMemberResponse])
def get_members(group_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    members = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).all()
    return members

@router.post("/{group_id}/channels", response_model=schemas.ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(group_id: str, channel: schemas.ChannelCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db_channel = models.Channel(
        group_id=group_id,
        name=channel.name
    )
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    return db_channel
