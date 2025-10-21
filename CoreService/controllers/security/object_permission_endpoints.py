# Object Permission Endpoints
# To be added to sys_sec_permission_mgmt_controller.py

# ==================== OBJECT PERMISSIONS (Record-Based) ====================

@sys_sec_permission_mgmt_router.get('/permissions/objects/type/{type_permission_id}', response_model=List[ObjectPermissionResponseDto])
async def get_type_object_permissions(
        type_permission_id: UUID,
        db: Session = Depends(get_db),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator'))
):
    """
    Get all object permissions for a specific type permission.
    Object permissions define criteria-based record-level access control.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    from repositories.security.sys_sec_object_permission_repository import SysSecObjectPermissionRepository

    try:
        permissions = SysSecObjectPermissionRepository.fetch_by_type_permission(db, type_permission_id)
        return [
            ObjectPermissionResponseDto(
                oid=perm.oid,
                criteria=perm.Criteria or "",
                read_state=perm.ReadState or 0,
                write_state=perm.WriteState or 0,
                delete_state=perm.DeleteState or 0,
                navigate_state=perm.NavigateState or 0,
                type_permission_object=perm.TypePermissionObject,
                optimistic_lock_field=perm.OptimisticLockField,
                gc_record=perm.GCRecord
            )
            for perm in permissions
        ]
    except Exception as e:
        logger.exception('Error fetching object permissions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error fetching object permissions: {str(e)}'
        )


@sys_sec_permission_mgmt_router.post('/permissions/objects', response_model=ObjectPermissionResponseDto, status_code=201)
async def create_object_permission(
        permission_request: ObjectPermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator'))
):
    """
    Create an object permission with criteria-based filtering.

    **Example Criteria:**
    - `[user_id] = CurrentUserId()` - Users can only see their own records
    - `[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()` - Users can see records they own or are assigned to
    - `[status] = 'active'` - Only active records
    - `[department_id] = CurrentUser().Department` - Records from user's department

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    from repositories.security.sys_sec_object_permission_repository import SysSecObjectPermissionRepository
    from repositories.security.sys_sec_type_permission_repository import SysSecTypePermissionRepository

    logger.info(f"Creating object permission for type permission {permission_request.type_permission_object}")

    # Validate type permission exists
    type_perm = SysSecTypePermissionRepository.fetch_by_id(db, permission_request.type_permission_object)
    if not type_perm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Type permission not found"
        )

    try:
        permission = SysSecObjectPermissionRepository.create(
            db=db,
            type_permission_id=permission_request.type_permission_object,
            criteria=permission_request.criteria or "",
            read_state=permission_request.read_state,
            write_state=permission_request.write_state,
            delete_state=permission_request.delete_state,
            navigate_state=permission_request.navigate_state
        )

        return ObjectPermissionResponseDto(
            oid=permission.oid,
            criteria=permission.Criteria or "",
            read_state=permission.ReadState or 0,
            write_state=permission.WriteState or 0,
            delete_state=permission.DeleteState or 0,
            navigate_state=permission.NavigateState or 0,
            type_permission_object=permission.TypePermissionObject,
            optimistic_lock_field=permission.OptimisticLockField,
            gc_record=permission.GCRecord
        )
    except Exception as e:
        logger.exception('Error creating object permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error creating object permission: {str(e)}'
        )


@sys_sec_permission_mgmt_router.put('/permissions/objects/{permission_id}', response_model=ObjectPermissionResponseDto)
async def update_object_permission(
        permission_id: UUID,
        permission_request: ObjectPermissionCreateDto,
        db: Session = Depends(get_db),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator'))
):
    """
    Update an object permission.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    from repositories.security.sys_sec_object_permission_repository import SysSecObjectPermissionRepository

    try:
        permission = SysSecObjectPermissionRepository.update(
            db=db,
            permission_id=permission_id,
            criteria=permission_request.criteria,
            read_state=permission_request.read_state,
            write_state=permission_request.write_state,
            delete_state=permission_request.delete_state,
            navigate_state=permission_request.navigate_state
        )

        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Object permission not found"
            )

        return ObjectPermissionResponseDto(
            oid=permission.oid,
            criteria=permission.Criteria or "",
            read_state=permission.ReadState or 0,
            write_state=permission.WriteState or 0,
            delete_state=permission.DeleteState or 0,
            navigate_state=permission.NavigateState or 0,
            type_permission_object=permission.TypePermissionObject,
            optimistic_lock_field=permission.OptimisticLockField,
            gc_record=permission.GCRecord
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error updating object permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error updating object permission: {str(e)}'
        )


@sys_sec_permission_mgmt_router.delete('/permissions/objects/{permission_id}')
async def delete_object_permission(
        permission_id: UUID,
        hard_delete: bool = False,
        db: Session = Depends(get_db),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator'))
):
    """
    Delete an object permission (soft delete by default).

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    from repositories.security.sys_sec_object_permission_repository import SysSecObjectPermissionRepository

    try:
        success = SysSecObjectPermissionRepository.delete(db, permission_id, hard_delete=hard_delete)

        if success:
            return {"message": "Object permission deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Object permission not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error deleting object permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error deleting object permission: {str(e)}'
        )
