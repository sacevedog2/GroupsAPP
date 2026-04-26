from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db import models
from app.schemas import groups as schemas
from app.core.events import publisher
from app.api.deps import get_current_user

router = APIRouter()

def get_group_or_404(group_id: str, db: Session) -> models.Group:
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

def get_channel_or_404(group_id: str, channel_id: str, db: Session) -> models.Channel:
    channel = db.query(models.Channel).filter(
        models.Channel.id == channel_id,
        models.Channel.group_id == group_id,
    ).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel

def normalize_user_id(user_id: str) -> str:
    return user_id.strip().lower()

def get_membership(group_id: str, user_id: str, db: Session) -> models.GroupMember | None:
    return db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == user_id,
    ).first()

def require_group_member(group_id: str, user_id: str, db: Session) -> models.GroupMember:
    membership = get_membership(group_id, user_id, db)
    if not membership:
        raise HTTPException(status_code=403, detail="Debes pertenecer al grupo.")
    return membership

def require_group_admin(group_id: str, user_id: str, db: Session) -> models.GroupMember:
    membership = require_group_member(group_id, user_id, db)
    if membership.role != models.RoleEnum.ADMIN.value:
        raise HTTPException(status_code=403, detail="Solo el admin del grupo puede hacer esta acción.")
    return membership

def require_channel_candidate(group_id: str, user_id: str, db: Session) -> str:
    normalized_user_id = normalize_user_id(user_id)
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="El usuario es obligatorio.")
    if not get_membership(group_id, normalized_user_id, db):
        raise HTTPException(status_code=400, detail="El usuario debe pertenecer al grupo antes de entrar al canal.")
    return normalized_user_id

def add_channel_member_record(
    group_id: str,
    channel_id: str,
    user_id: str,
    db: Session,
) -> models.ChannelMember:
    normalized_user_id = require_channel_candidate(group_id, user_id, db)
    existing_member = db.query(models.ChannelMember).filter(
        models.ChannelMember.channel_id == channel_id,
        models.ChannelMember.user_id == normalized_user_id,
    ).first()
    if existing_member:
        return existing_member

    channel_member = models.ChannelMember(
        channel_id=channel_id,
        group_id=group_id,
        user_id=normalized_user_id,
    )
    db.add(channel_member)
    return channel_member

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
            detail="Para crear un grupo debes agregar al menos 2 usuarios.",
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
    group = get_group_or_404(group_id, db)
    require_group_member(group_id, current_user_id, db)
    return group

@router.patch("/{group_id}", response_model=schemas.GroupResponse)
def update_group(group_id: str, group_update: schemas.GroupUpdate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    group = get_group_or_404(group_id, db)
    require_group_admin(group_id, current_user_id, db)

    if group_update.name is not None:
        name = group_update.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="El nombre del grupo no puede estar vacío.")
        group.name = name
    if group_update.description is not None:
        group.description = group_update.description.strip() or None
    if group_update.settings is not None:
        group.settings = group_update.settings

    db.commit()
    db.refresh(group)
    publisher.publish("group.updated", {
        "group_id": group.id,
        "name": group.name,
        "description": group.description,
        "actor_user_id": current_user_id,
    })
    return group

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    group = get_group_or_404(group_id, db)
    require_group_admin(group_id, current_user_id, db)
    db.delete(group)
    db.commit()
    publisher.publish("group.deleted", {
        "group_id": group_id,
        "actor_user_id": current_user_id,
    })
    return None

@router.post("/{group_id}/members", response_model=schemas.GroupMemberResponse)
def add_member(group_id: str, member: schemas.GroupMemberCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    require_group_admin(group_id, current_user_id, db)
    normalized_user_id = normalize_user_id(member.user_id)
    if not normalized_user_id:
        raise HTTPException(status_code=400, detail="El usuario es obligatorio.")
        
    db_member = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == normalized_user_id
    ).first()
    if db_member:
        raise HTTPException(status_code=400, detail="User is already a member")

    new_member = models.GroupMember(
        group_id=group_id,
        user_id=normalized_user_id,
        role=models.RoleEnum.MEMBER.value
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
    get_group_or_404(group_id, db)
    require_group_member(group_id, current_user_id, db)
    members = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).all()
    return members

@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(group_id: str, user_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    require_group_admin(group_id, current_user_id, db)
    normalized_user_id = normalize_user_id(user_id)
    member = get_membership(group_id, normalized_user_id, db)
    if not member:
        raise HTTPException(status_code=404, detail="User is not a member")

    if member.role == models.RoleEnum.ADMIN.value:
        admin_count = db.query(models.GroupMember).filter(
            models.GroupMember.group_id == group_id,
            models.GroupMember.role == models.RoleEnum.ADMIN.value,
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="No puedes eliminar al único admin del grupo.")

    db.query(models.ChannelMember).filter(
        models.ChannelMember.group_id == group_id,
        models.ChannelMember.user_id == normalized_user_id,
    ).delete(synchronize_session=False)
    db.delete(member)
    db.commit()
    publisher.publish("member.removed", {
        "group_id": group_id,
        "user_id": normalized_user_id,
        "actor_user_id": current_user_id,
    })
    return None

@router.get("/{group_id}/channels", response_model=List[schemas.ChannelResponse])
def get_channels(group_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    require_group_member(group_id, current_user_id, db)
    return db.query(models.Channel).filter(models.Channel.group_id == group_id).all()

@router.post("/{group_id}/channels", response_model=schemas.ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(group_id: str, channel: schemas.ChannelCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    require_group_admin(group_id, current_user_id, db)
    name = channel.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del canal no puede estar vacío.")

    existing_channel = db.query(models.Channel).filter(
        models.Channel.group_id == group_id,
        models.Channel.name == name,
    ).first()
    if existing_channel:
        raise HTTPException(status_code=400, detail="Ya existe un canal con ese nombre en el grupo.")

    db_channel = models.Channel(
        group_id=group_id,
        name=name
    )
    db.add(db_channel)
    db.flush()

    member_ids = []
    for user_id in [current_user_id, *channel.member_ids]:
        normalized_user_id = normalize_user_id(user_id)
        if normalized_user_id and normalized_user_id not in member_ids:
            member_ids.append(normalized_user_id)

    for user_id in member_ids:
        add_channel_member_record(group_id, db_channel.id, user_id, db)

    db.commit()
    db.refresh(db_channel)
    publisher.publish("channel.created", {
        "group_id": group_id,
        "channel_id": db_channel.id,
        "name": db_channel.name,
        "member_ids": member_ids,
        "actor_user_id": current_user_id,
    })
    return db_channel

@router.get("/{group_id}/channels/{channel_id}/members", response_model=List[schemas.ChannelMemberResponse])
def get_channel_members(group_id: str, channel_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    get_channel_or_404(group_id, channel_id, db)
    require_group_member(group_id, current_user_id, db)
    return db.query(models.ChannelMember).filter(
        models.ChannelMember.group_id == group_id,
        models.ChannelMember.channel_id == channel_id,
    ).all()

@router.post("/{group_id}/channels/{channel_id}/members", response_model=schemas.ChannelMemberResponse, status_code=status.HTTP_201_CREATED)
def add_channel_member(group_id: str, channel_id: str, member: schemas.ChannelMemberCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    get_channel_or_404(group_id, channel_id, db)
    require_group_admin(group_id, current_user_id, db)
    normalized_user_id = require_channel_candidate(group_id, member.user_id, db)
    existing_member = db.query(models.ChannelMember).filter(
        models.ChannelMember.channel_id == channel_id,
        models.ChannelMember.user_id == normalized_user_id,
    ).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a channel member")

    channel_member = models.ChannelMember(
        channel_id=channel_id,
        group_id=group_id,
        user_id=normalized_user_id,
    )
    db.add(channel_member)
    db.commit()
    db.refresh(channel_member)
    publisher.publish("channel.member.added", {
        "group_id": group_id,
        "channel_id": channel_id,
        "user_id": normalized_user_id,
        "actor_user_id": current_user_id,
    })
    return channel_member

@router.delete("/{group_id}/channels/{channel_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_channel_member(group_id: str, channel_id: str, user_id: str, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    get_group_or_404(group_id, db)
    get_channel_or_404(group_id, channel_id, db)
    require_group_admin(group_id, current_user_id, db)
    normalized_user_id = normalize_user_id(user_id)
    channel_member = db.query(models.ChannelMember).filter(
        models.ChannelMember.channel_id == channel_id,
        models.ChannelMember.user_id == normalized_user_id,
    ).first()
    if not channel_member:
        raise HTTPException(status_code=404, detail="User is not a channel member")

    db.delete(channel_member)
    db.commit()
    publisher.publish("channel.member.removed", {
        "group_id": group_id,
        "channel_id": channel_id,
        "user_id": normalized_user_id,
        "actor_user_id": current_user_id,
    })
    return None
