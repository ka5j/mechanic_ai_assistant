# io_adapters/console_adapter.py

class ConsoleAdapter:
    """
    A command-line IO adapter for process_interaction:
      - prompt(text): prints the assistant’s message
      - collect(prompt_text): prints the prompt_text (without newline),
                              reads a line from stdin, and returns it.
    """
    def prompt(self, text: str):
        # Assistant says something
        print(text)

    def collect(self, prompt_text: str) -> str:
        # Ask the user; return their response (empty string if they just hit enter)
        return input(prompt_text).strip()
