"""
Custom hooks for drf-spectacular to customize OpenAPI schema.
"""


def remove_extra_security_schemes(result, generator, request, public):
    """Remove auto-detected security schemes, keep only TokenAuth."""
    if 'components' in result and 'securitySchemes' in result['components']:
        # Keep only TokenAuth
        result['components']['securitySchemes'] = {
            'TokenAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'Token-based authentication. Format: `Token <your-token>`'
            }
        }
    return result
