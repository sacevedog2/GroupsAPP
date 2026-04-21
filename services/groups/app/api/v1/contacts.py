from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db import models
from app.schemas import contacts as schemas
from app.api.deps import get_current_user

router = APIRouter()

# Authenticated endpoints
@router.post("/", response_model=schemas.ContactResponse, status_code=status.HTTP_201_CREATED)
def add_contact(contact: schemas.ContactCreate, current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Validation: check if they share a group
    shared_group = db.query(models.GroupMember).join(
        models.GroupMember, models.GroupMember.group_id == models.GroupMember.group_id
    ).filter(
        models.GroupMember.user_id == current_user_id,
        models.GroupMember.user_id == contact.contact_user_id
    ).first()

    # We can do this simpler by finding intersection of their group IDs:
    owner_groups = db.query(models.GroupMember.group_id).filter(models.GroupMember.user_id == current_user_id).subquery()
    contact_groups = db.query(models.GroupMember.group_id).filter(models.GroupMember.user_id == contact.contact_user_id).subquery()
    
    shared = db.query(owner_groups).join(contact_groups, owner_groups.c.group_id == contact_groups.c.group_id).first()

    if not shared:
        raise HTTPException(
            status_code=400, 
            detail="Cannot add contact. Users do not share any group."
        )

    # 2. Add contact
    existing_contact = db.query(models.Contact).filter(
        models.Contact.owner_id == current_user_id,
        models.Contact.contact_user_id == contact.contact_user_id
    ).first()
    
    if existing_contact:
         raise HTTPException(status_code=400, detail="Contact already exists")

    new_contact = models.Contact(
        owner_id=current_user_id,
        contact_user_id=contact.contact_user_id,
        alias=contact.alias
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

@router.get("/", response_model=List[schemas.ContactResponse])
def get_contacts(current_user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    contacts = db.query(models.Contact).filter(models.Contact.owner_id == current_user_id).all()
    return contacts
