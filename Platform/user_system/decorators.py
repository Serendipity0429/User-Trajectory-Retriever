from functools import wraps

def consent_exempt(view_func):
    """
    Mark a view function as being exempt from the informed consent enforcement.
    """
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    
    # Set the exempt flag
    wrapped_view.consent_exempt = True
    return wrapped_view