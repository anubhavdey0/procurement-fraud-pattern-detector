"""bidscreen: collusion screens for public tender data.

Everything this package produces is a lead for a human to review. A screen
firing says that a pattern in the data is unusual under a stated null model.
It does not say that anyone broke the law.
"""

from bidscreen.model import Market

__all__ = ["Market", "__version__"]
__version__ = "0.1.0"
