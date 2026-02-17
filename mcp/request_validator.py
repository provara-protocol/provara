"""
request_validator.py — JSON-RPC request validation for MCP server

Validates request structure and tool arguments against schemas.
"""

from typing import Any, Dict, List, Optional, Tuple


def validate_jsonrpc_request(request: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate basic JSON-RPC 2.0 request structure.
    
    Returns:
        (is_valid, error_message)
    """
    # Check jsonrpc version
    if request.get("jsonrpc") != "2.0":
        return False, "Invalid or missing 'jsonrpc' field (must be '2.0')"
    
    # Check method
    method = request.get("method")
    if not method or not isinstance(method, str):
        return False, "Missing or invalid 'method' field"
    
    # Check id (optional for notifications, but we require it)
    if "id" not in request:
        return False, "Missing 'id' field"
    
    # Check params (optional, but must be object if present)
    params = request.get("params")
    if params is not None and not isinstance(params, dict):
        return False, "'params' must be an object if present"
    
    return True, None


def validate_tool_arguments(tool_name: str, args: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate tool arguments against input schema.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in args:
            errors.append(f"Missing required argument: {field}")
    
    # Check field types
    properties = schema.get("properties", {})
    for field_name, field_value in args.items():
        if field_name not in properties:
            errors.append(f"Unknown argument: {field_name}")
            continue
        
        prop_schema = properties[field_name]
        expected_type = prop_schema.get("type")
        
        if expected_type == "string" and not isinstance(field_value, str):
            errors.append(f"Argument '{field_name}' must be a string")
        elif expected_type == "boolean" and not isinstance(field_value, bool):
            errors.append(f"Argument '{field_name}' must be a boolean")
        elif expected_type == "number" and not isinstance(field_value, (int, float)):
            errors.append(f"Argument '{field_name}' must be a number")
        elif expected_type == "object" and not isinstance(field_value, dict):
            errors.append(f"Argument '{field_name}' must be an object")
        elif expected_type == "array" and not isinstance(field_value, list):
            errors.append(f"Argument '{field_name}' must be an array")
    
    return len(errors) == 0, errors


def validate_path_argument(path_str: str) -> Tuple[bool, Optional[str]]:
    """
    Basic path validation to prevent directory traversal.
    
    Returns:
        (is_valid, error_message)
    """
    # Check for directory traversal attempts
    if ".." in path_str:
        return False, "Path must not contain '..' (directory traversal)"
    
    # Check for absolute path indicators that might be suspicious
    # (This is basic; in production you'd want more robust validation)
    if any(dangerous in path_str for dangerous in ["~", "$", "`"]):
        return False, "Path contains potentially dangerous characters"
    
    return True, None
