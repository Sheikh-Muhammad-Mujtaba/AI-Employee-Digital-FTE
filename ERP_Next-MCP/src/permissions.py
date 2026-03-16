import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path


class PermissionManager:
    def __init__(self, config: Dict):
        self.config = config
        self.audit_enabled = config.get('audit', {}).get('enabled', True)
        self.audit_log = config.get('audit', {}).get('log_file', 'logs/audit.log')
        self.log_level = config.get('audit', {}).get('log_level', 'INFO')

        # Always create a logger; if audit is disabled it won't write anywhere
        self.logger = logging.getLogger(f"{__name__}.audit")

        if self.audit_enabled:
            log_dir = Path(self.audit_log).parent
            log_dir.mkdir(parents=True, exist_ok=True)

            handler = logging.FileHandler(self.audit_log)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
            ))
            handler.setLevel(getattr(logging, self.log_level.upper()))
            self.logger.addHandler(handler)
            self.logger.setLevel(getattr(logging, self.log_level.upper()))
    
    def _get_doctype_permissions(self, doctype: str) -> Dict:
        doctypes_config = self.config.get('permissions', {}).get('doctypes', {})
        default_config = self.config.get('permissions', {}).get('default', {})

        # Exact match first
        if doctype in doctypes_config:
            return doctypes_config[doctype]

        # Case-insensitive fallback (handles "customer" vs "Customer")
        doctype_lower = doctype.lower()
        for key, value in doctypes_config.items():
            if key.lower() == doctype_lower:
                return value

        return default_config
    
    def can_read(self, doctype: str) -> bool:
        permissions = self._get_doctype_permissions(doctype)
        return permissions.get('read', False)
    
    def can_create(self, doctype: str) -> bool:
        permissions = self._get_doctype_permissions(doctype)
        return permissions.get('create', False)
    
    def can_update(self, doctype: str) -> bool:
        permissions = self._get_doctype_permissions(doctype)
        return permissions.get('update', False)
    
    def can_delete(self, doctype: str) -> bool:
        permissions = self._get_doctype_permissions(doctype)
        return permissions.get('delete', False)
    
    def filter_allowed_fields(self, data: Dict, doctype: str) -> Dict:
        permissions = self._get_doctype_permissions(doctype)
        allowed_fields = permissions.get('allowed_fields', [])
        restricted_fields = permissions.get('restricted_fields', [])
        
        if not allowed_fields:
            filtered_data = {k: v for k, v in data.items() if k not in restricted_fields}
        else:
            filtered_data = {
                k: v for k, v in data.items() 
                if k in allowed_fields and k not in restricted_fields
            }
        
        return filtered_data
    
    def check_field_permission(self, doctype: str, field: str, operation: str = 'read') -> bool:
        permissions = self._get_doctype_permissions(doctype)
        allowed_fields = permissions.get('allowed_fields', [])
        restricted_fields = permissions.get('restricted_fields', [])
        

        if field in restricted_fields:
            return False
        
        if not allowed_fields:
            return True
        
        return field in allowed_fields
    
    def validate_conditions(self, doctype: str, operation: str, data: Optional[Dict] = None) -> Tuple[bool, str]:
        permissions = self._get_doctype_permissions(doctype)
        conditions = permissions.get('conditions', {}).get(operation, {})
        
        if not conditions or not data:
            return True, ""
        
        for field, allowed_values in conditions.items():
            if field in data:
                value = data[field]
                if isinstance(allowed_values, list):
                    if value not in allowed_values:
                        return False, f"Field '{field}' value '{value}' not in allowed values: {allowed_values}"
                elif isinstance(allowed_values, dict):
                    if 'in' in allowed_values and value not in allowed_values['in']:
                        return False, f"Field '{field}' value '{value}' not in allowed values"
                    if 'not_in' in allowed_values and value in allowed_values['not_in']:
                        return False, f"Field '{field}' value '{value}' is in forbidden values"
                    if 'min' in allowed_values and value < allowed_values['min']:
                        return False, f"Field '{field}' value '{value}' below minimum: {allowed_values['min']}"
                    if 'max' in allowed_values and value > allowed_values['max']:
                        return False, f"Field '{field}' value '{value}' above maximum: {allowed_values['max']}"
        
        return True, ""
    
    def validate_operation(self, operation: str, doctype: str, data: Optional[Dict] = None, 
                          document_name: Optional[str] = None) -> Tuple[bool, str]:
        operation = operation.lower()
        
        allowed = False
        if operation == 'read':
            allowed = self.can_read(doctype)
        elif operation == 'create':
            allowed = self.can_create(doctype)
        elif operation == 'update':
            allowed = self.can_update(doctype)
        elif operation == 'delete':
            allowed = self.can_delete(doctype)
        else:
            return False, f"Unknown operation: {operation}"
        
        if not allowed:
            reason = f"Operation '{operation}' not allowed for doctype '{doctype}'"
            self._log_operation(operation, doctype, False, reason, data, document_name)
            return False, reason
        
        if data:
            conditions_valid, condition_reason = self.validate_conditions(doctype, operation, data)
            if not conditions_valid:
                self._log_operation(operation, doctype, False, condition_reason, data, document_name)
                return False, condition_reason
        
        self._log_operation(operation, doctype, True, "Operation allowed", data, document_name)
        return True, ""
    
    def _log_operation(self, operation: str, doctype: str, allowed: bool, reason: str, 
                      data: Optional[Dict] = None, document_name: Optional[str] = None):
        if not self.audit_enabled:
            return
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation.upper(),
            "doctype": doctype,
            "allowed": allowed,
            "reason": reason,
            "document_name": document_name,
            "data_keys": list(data.keys()) if data else None,
            "field_count": len(data) if data else 0
        }
        
        log_message = (
            f"Operation: {operation.upper()} | DocType: {doctype} | "
            f"Result: {'ALLOWED' if allowed else 'DENIED'} | Reason: {reason}"
        )
        
        if document_name:
            log_message += f" | Document: {document_name}"
        
        if data:
            log_message += f" | Fields: {list(data.keys())}"
        
        if allowed:
            self.logger.info(log_message)
        else:
            self.logger.warning(log_message)
    
    def get_allowed_operations(self, doctype: str) -> List[str]:
        operations = []
        if self.can_read(doctype):
            operations.append('read')
        if self.can_create(doctype):
            operations.append('create')
        if self.can_update(doctype):
            operations.append('update')
        if self.can_delete(doctype):
            operations.append('delete')
        return operations
    
    def get_allowed_fields(self, doctype: str) -> List[str]:
        permissions = self._get_doctype_permissions(doctype)
        allowed_fields = permissions.get('allowed_fields', [])
        restricted_fields = permissions.get('restricted_fields', [])
        
        # Remove restricted fields from allowed fields
        return [field for field in allowed_fields if field not in restricted_fields]
    
    def get_doctype_summary(self, doctype: str) -> Dict:
        permissions = self._get_doctype_permissions(doctype)
        
        return {
            "doctype": doctype,
            "operations": self.get_allowed_operations(doctype),
            "allowed_fields": self.get_allowed_fields(doctype),
            "restricted_fields": permissions.get('restricted_fields', []),
            "conditions": permissions.get('conditions', {}),
            "field_count": len(self.get_allowed_fields(doctype))
        }
    
    def get_all_doctypes(self) -> List[str]:
        return list(self.config.get('permissions', {}).get('doctypes', {}).keys())
    
    def export_permissions(self) -> Dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "permissions": self.config.get('permissions', {}),
            "audit_enabled": self.audit_enabled,
            "configured_doctypes": self.get_all_doctypes()
        }