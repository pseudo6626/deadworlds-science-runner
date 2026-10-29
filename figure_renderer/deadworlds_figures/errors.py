class FigureSpecError(ValueError):
    """FigureSpec contract or scientific-rendering policy violation."""


class UnsupportedRecipeError(FigureSpecError):
    """The renderer does not yet implement the requested recipe."""
