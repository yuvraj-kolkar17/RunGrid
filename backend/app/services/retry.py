def calculate_delay(strategy: str, base_delay: int, attempt: int) -> int:
    """Calculate the retry delay in seconds based on the strategy and attempt count.
    
    Args:
        strategy: One of 'fixed', 'linear', or 'exponential'.
        base_delay: The base delay in seconds. Must be >= 0.
        attempt: The 1-based number of execution attempts that have actually started.
        
    Returns:
        The calculated delay in seconds.
    """
    if base_delay < 0:
        raise ValueError("base_delay must be non-negative")
    if attempt <= 0:
        raise ValueError("attempt must be greater than 0")
        
    if strategy == "fixed":
        return base_delay
    elif strategy == "linear":
        return base_delay * attempt
    elif strategy == "exponential":
        return base_delay * (2 ** (attempt - 1))
    else:
        raise ValueError(f"Unknown retry strategy: {strategy}")
