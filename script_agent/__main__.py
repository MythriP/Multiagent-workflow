"""Allow `python -m script_agent` to behave like `python -m script_agent.run`."""

from .run import main

if __name__ == "__main__":
    main()
