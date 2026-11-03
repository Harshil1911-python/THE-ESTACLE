"""Tool schemas and registry for Estacle AI."""
from routes.ai_tools_funcs import (
    tool_list_clients, tool_create_client, tool_update_client,
    tool_list_properties, tool_create_property, tool_update_property,
    tool_list_users, tool_create_user, tool_schedule_appointment,
    tool_create_task, tool_list_tasks, tool_create_deal,
    tool_search, tool_get_stats,
)

TOOL_IMPL = {
    'list_clients': tool_list_clients,
    'create_client': tool_create_client,
    'update_client': tool_update_client,
    'list_properties': tool_list_properties,
    'create_property': tool_create_property,
    'update_property': tool_update_property,
    'list_users': tool_list_users,
    'create_user': tool_create_user,
    'schedule_appointment': tool_schedule_appointment,
    'create_task': tool_create_task,
    'list_tasks': tool_list_tasks,
    'create_deal': tool_create_deal,
    'search': tool_search,
    'get_stats': tool_get_stats,
}

GEMINI_TOOLS = [
    {'name': 'list_clients', 'description': 'List clients/leads in the CRM.', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_client', 'description': 'Create a new client or lead.', 'parameters': {'type': 'object', 'properties': {'full_name': {'type': 'string'}, 'email': {'type': 'string'}, 'phone': {'type': 'string'}, 'status': {'type': 'string'}, 'notes': {'type': 'string'}, 'budget': {'type': 'number'}, 'preferred_city': {'type': 'string'}, 'source': {'type': 'string'}}, 'required': ['full_name']}},
    {'name': 'update_client', 'description': 'Update an existing client by id.', 'parameters': {'type': 'object', 'properties': {'client_id': {'type': 'integer'}, 'full_name': {'type': 'string'}, 'email': {'type': 'string'}, 'phone': {'type': 'string'}, 'status': {'type': 'string'}, 'notes': {'type': 'string'}, 'budget': {'type': 'number'}}, 'required': ['client_id']}},
    {'name': 'list_properties', 'description': 'List properties.', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}, 'city': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_property', 'description': 'Add a new property listing.', 'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'price': {'type': 'number'}, 'property_type': {'type': 'string'}, 'status': {'type': 'string'}, 'listing_type': {'type': 'string'}, 'city': {'type': 'string'}, 'address': {'type': 'string'}, 'bedrooms': {'type': 'integer'}, 'bathrooms': {'type': 'number'}, 'area_sqft': {'type': 'number'}, 'description': {'type': 'string'}}, 'required': ['title', 'price']}},
    {'name': 'update_property', 'description': 'Update property fields by id.', 'parameters': {'type': 'object', 'properties': {'property_id': {'type': 'integer'}, 'title': {'type': 'string'}, 'price': {'type': 'number'}, 'status': {'type': 'string'}, 'city': {'type': 'string'}}, 'required': ['property_id']}},
    {'name': 'list_users', 'description': 'List system users.', 'parameters': {'type': 'object', 'properties': {'role': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_user', 'description': 'Create a new user account.', 'parameters': {'type': 'object', 'properties': {'full_name': {'type': 'string'}, 'email': {'type': 'string'}, 'password': {'type': 'string'}, 'role': {'type': 'string'}, 'phone': {'type': 'string'}}, 'required': ['full_name', 'email', 'password']}},
    {'name': 'schedule_appointment', 'description': 'Schedule a viewing. Date: YYYY-MM-DD HH:MM.', 'parameters': {'type': 'object', 'properties': {'client_id': {'type': 'integer'}, 'client_name': {'type': 'string'}, 'property_id': {'type': 'integer'}, 'agent_id': {'type': 'integer'}, 'appointment_date': {'type': 'string'}, 'notes': {'type': 'string'}}, 'required': ['appointment_date']}},
    {'name': 'create_task', 'description': 'Create a follow-up task.', 'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'description': {'type': 'string'}, 'due_date': {'type': 'string'}, 'priority': {'type': 'string'}, 'assigned_to': {'type': 'integer'}, 'related_client_id': {'type': 'integer'}}, 'required': ['title']}},
    {'name': 'list_tasks', 'description': 'List tasks.', 'parameters': {'type': 'object', 'properties': {'status': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
    {'name': 'create_deal', 'description': 'Create a deal in the pipeline.', 'parameters': {'type': 'object', 'properties': {'title': {'type': 'string'}, 'value': {'type': 'number'}, 'stage': {'type': 'string'}, 'client_id': {'type': 'integer'}, 'property_id': {'type': 'integer'}, 'notes': {'type': 'string'}}, 'required': ['title']}},
    {'name': 'search', 'description': 'Search clients, properties and users.', 'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}, 'limit': {'type': 'integer'}}, 'required': ['query']}},
    {'name': 'get_stats', 'description': 'Get high-level CRM counts.', 'parameters': {'type': 'object', 'properties': {}}},
]

SYSTEM_PROMPT = """You are Estacle AI, the intelligent assistant for the Estacle Real Estate CRM.
Use tools for all data operations. Never invent IDs. Be concise.
Dates: appointments YYYY-MM-DD HH:MM, tasks YYYY-MM-DD. Currency often INR.
"""
