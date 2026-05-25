"""Allow `python -m sourcing_agent` to behave like `python -m sourcing_agent.run`."""

from .run import main

if __name__ == "__main__":
    main()
