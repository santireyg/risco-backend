# app/api/endpoints/user_management.py

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    status,
)
from bson import ObjectId

from app.core.auth import (
    get_admin_or_superadmin_user,
    can_manage_user,
)
from app.core.database import users_collection
from app.core.limiter import limiter
from app.models.users import User, UserPublic
from app.utils.email_utils import send_welcome_email

router = APIRouter()
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# LISTADO DE USUARIOS PENDIENTES
# ────────────────────────────────────────────────────────────────

@router.get("/pending-users", response_model=List[UserPublic])
async def get_pending_users(
    current_user: User = Depends(get_admin_or_superadmin_user)
):
    """
    Lista usuarios pendientes de aprobación.
    Requiere rol admin o superadmin.
    """
    try:
        # Buscar usuarios con status pending_approval
        cursor = users_collection.find({
            "status": "pending_approval",
            "email_verified": True
        }).sort("created_at", 1)
        
        users = []
        async for user_data in cursor:
            users.append(UserPublic(**user_data))
        
        logger.info(f"Admin {current_user.username} consultó usuarios pendientes: {len(users)} encontrados")
        
        return users

    except Exception as e:
        logger.error(f"Error obteniendo usuarios pendientes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# APROBAR USUARIO
# ────────────────────────────────────────────────────────────────

@router.post("/approve-user/{user_id}", response_model=dict)
async def approve_user(
    user_id: str,
    current_user: User = Depends(get_admin_or_superadmin_user)
):
    """
    Aprueba un usuario pendiente.
    Cambia status de pending_approval -> active.
    """
    try:
        # Validar ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de usuario inválido"
            )

        # Buscar usuario pendiente
        user_data = await users_collection.find_one({
            "_id": ObjectId(user_id),
            "status": "pending_approval"
        })
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario pendiente no encontrado"
            )

        # Actualizar status a active
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "status": "active",
                    "approved_at": datetime.utcnow(),
                    "approved_by": current_user.username,
                }
            }
        )

        # Enviar email de bienvenida
        email_sent = await send_welcome_email(user_data)
        
        if not email_sent:
            logger.warning(f"No se pudo enviar email de bienvenida a {user_data['email']}")

        logger.info(f"Usuario {user_data['username']} aprobado por admin {current_user.username}")
        
        return {
            "message": f"Usuario {user_data['username']} aprobado exitosamente",
            "username": user_data["username"],
            "email_sent": email_sent
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error aprobando usuario {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# RECHAZAR USUARIO (OPCIONAL)
# ────────────────────────────────────────────────────────────────

@router.post("/reject-user/{user_id}", response_model=dict)
async def reject_user(
    user_id: str,
    reason: Optional[str] = Form(None),
    current_user: User = Depends(get_admin_or_superadmin_user)
):
    """
    Rechaza un usuario pendiente.
    Cambia status de pending_approval -> rejected.
    """
    try:
        # Validar ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de usuario inválido"
            )

        # Buscar usuario pendiente
        user_data = await users_collection.find_one({
            "_id": ObjectId(user_id),
            "status": "pending_approval"
        })
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario pendiente no encontrado"
            )

        # Actualizar status a rejected
        update_data = {
            "status": "rejected",
            "rejected_at": datetime.utcnow(),
            "rejected_by": current_user.username,
        }
        
        if reason:
            update_data["rejection_reason"] = reason

        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

        logger.info(f"Usuario {user_data['username']} rechazado por admin {current_user.username}")
        
        return {
            "message": f"Usuario {user_data['username']} rechazado",
            "username": user_data["username"],
            "reason": reason
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error rechazando usuario {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# LISTADO DE USUARIOS REGISTRADOS
# ────────────────────────────────────────────────────────────────

@router.get("/users", response_model=dict)
@limiter.limit("20/minute")
async def get_registered_users(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    role_filter: Optional[str] = Query(None, alias="role"),
    current_user: User = Depends(get_admin_or_superadmin_user)
):
    """
    Lista usuarios registrados con paginación y filtros.
    Admin no ve usuarios superadmin.
    Superadmin ve todos los usuarios incluyendo otros superadmin.
    """
    try:
        # Construir filtros de búsqueda
        query = {}
        
        # Excluir usuarios eliminados (soft delete)
        query["status"] = {"$ne": "deleted"}
        
        # Filtros de visibilidad por rol
        if current_user.role == "admin":
            # Admin solo ve users y otros admin (no superadmin)
            query["role"] = {"$in": ["user", "admin"]}
        # Superadmin puede ver todos los usuarios (incluyendo otros superadmin)
        # No se aplica filtro de rol para superadmin

        # Filtro por status
        if status_filter:
            query["status"] = status_filter

        # Filtro por rol
        if role_filter:
            if current_user.role == "admin" and role_filter == "superadmin":
                # Admin no puede filtrar por superadmin
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para ver usuarios superadmin"
                )
            query["role"] = role_filter

        # Contar total de usuarios
        total_users = await users_collection.count_documents(query)
        
        # Calcular paginación
        skip = (page - 1) * limit
        total_pages = (total_users + limit - 1) // limit

        # Obtener usuarios paginados
        cursor = users_collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        users = []
        async for user_data in cursor:
            users.append(UserPublic(**user_data))

        logger.info(f"Admin {current_user.username} consultó usuarios registrados: página {page}")
        
        return {
            "users": users,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_users": total_users,
                "page_size": limit,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "filters": {
                "status": status_filter,
                "role": role_filter
            }
        }

    except Exception as e:
        logger.error(f"Error obteniendo usuarios registrados: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )


# ────────────────────────────────────────────────────────────────
# GESTIONAR USUARIO
# ────────────────────────────────────────────────────────────────

@router.put("/manage-user/{user_id}", response_model=dict)
@limiter.limit("10/minute")
async def manage_user(
    request: Request,
    user_id: str,
    action: str = Form(...),  # "deactivate" | "activate" | "change_role" | "delete"
    new_role: Optional[str] = Form(None),  # Solo para change_role
    current_user: User = Depends(get_admin_or_superadmin_user)
):
    """
    Gestiona usuarios: activar, desactivar, cambiar rol, eliminar.
    Respeta la jerarquía de permisos.
    """
    try:
        # Validar ObjectId
        if not ObjectId.is_valid(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de usuario inválido"
            )

        # Validar acción
        valid_actions = ["deactivate", "activate", "change_role", "delete"]
        if action not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Acción inválida. Debe ser una de: {', '.join(valid_actions)}"
            )

        # Buscar usuario objetivo
        target_user_data = await users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not target_user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        target_user = User(**target_user_data)

        # Verificar permisos para gestionar este usuario
        if not can_manage_user(current_user, target_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para gestionar este usuario"
            )

        # Ejecutar acción
        update_data = {}
        action_description = ""

        if action == "deactivate":
            if target_user.status == "inactive":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario ya está desactivado"
                )
            update_data = {
                "status": "inactive",
                "deactivated_by": current_user.username,
                "deactivated_at": datetime.utcnow(),
            }
            action_description = "desactivado"

        elif action == "activate":
            if target_user.status == "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario ya está activo"
                )
            update_data = {
                "status": "active",
                "deactivated_by": None,
                "deactivated_at": None,
            }
            action_description = "activado"

        elif action == "change_role":
            if not new_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Se requiere especificar el nuevo rol"
                )
            
            valid_roles = ["user", "admin"]
            if current_user.role == "admin" and new_role not in ["user"]:
                # Admin solo puede cambiar a user
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes asignar el rol 'user'"
                )
            elif current_user.role == "superadmin" and new_role not in valid_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Rol inválido. Debe ser uno de: {', '.join(valid_roles)}"
                )

            if target_user.role == new_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El usuario ya tiene el rol '{new_role}'"
                )

            update_data = {
                "role": new_role,
                "role_changed_by": current_user.username,
                "role_changed_at": datetime.utcnow(),
            }
            action_description = f"rol cambiado de '{target_user.role}' a '{new_role}'"

        elif action == "delete":
            if target_user.status == "deleted":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario ya está eliminado"
                )
            update_data = {
                "status": "deleted",
                "deleted_by": current_user.username,
                "deleted_at": datetime.utcnow(),
            }
            action_description = "eliminado"

        # Actualizar usuario
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

        logger.info(f"Usuario {target_user.username} {action_description} por admin {current_user.username}")
        
        return {
            "message": f"Usuario {target_user.username} {action_description} exitosamente",
            "username": target_user.username,
            "action": action,
            "details": action_description
        }

    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except Exception as e:
        logger.error(f"Error gestionando usuario {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )
