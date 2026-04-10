from sqlmodel import Session, select

from db.models import UserRole


def assign_role(session: Session, user_id: int, role: str) -> UserRole:
    ur = UserRole(user_id=user_id, role=role)
    session.add(ur)
    session.commit()
    session.refresh(ur)
    return ur


def revoke_role(session: Session, user_id: int, role: str) -> None:
    row = session.exec(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role)
    ).first()
    if row:
        session.delete(row)
        session.commit()


def get_roles(session: Session, user_id: int) -> list[str]:
    return [r.role for r in session.exec(select(UserRole).where(UserRole.user_id == user_id)).all()]
