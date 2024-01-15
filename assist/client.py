"""
An OpenAI Assistant that can leverage models, tools, and knowledge
to respond to user queries.

Dec 2023, Timo Koehler
"""

import dotenv
import logging
import argparse
from assistant import OpenAIAssistant, ConversationFactory
from tools.functioncalling import Schemas

"""
Assistant level settings
    - Model
    - Instructions: to guide the personality of the Assistant and define
                    its goals (system prompt).
    - Functions:    third-party tools integration via a function calling.
    - Files:        tools access to own domain data.
"""
traiage_args = {
    "name": "Traiage",
    "instructions": """You are a root-cause analyst and your task is to
    analyze system log files for software issues like failure events
    or critical conditions and their initial root cause or trigger.

    Task 1: Process files and look for this pattern, example,
    ERROR  rq.worker    Traceback (most recent call last).

    Task 2: After you find these patterns, correlate with any log
    messages with a lower timestamp and with matching IP address.
    Do not consider recurring log messages if they contain or represent a failure.

    Task 3: Summarize the results in a bullet list containing timestamps
    in ascending order and including data from the log message.""",

    "model": "gpt-4-1106-preview",
    # "model": "gpt-3.5-turbo-1106",
    "functions": [
        "Schemas.getSummary",
        "Schemas.getTimestampDelta",
        "Schemas.getLogSeveritySubject",
        "Schemas.getIpAddress",
    ],
    "tools": [
        {"type": "code_interpreter"},
        {"type": "function", "function": Schemas.getSummary},
        {"type": "function", "function": Schemas.getTimestampDelta},
        {"type": "function", "function": Schemas.getLogSeveritySubject},
        {"type": "function", "function": Schemas.getIpAddress},
    ],
    "files": [
        "/home/tikoehle/work/outshift/log_analysis/data/test2.csv",
    ],
}

"""
Thread (message) level settings
    - additional instructions specific to the assistent and message.
"""
message_instructions = """
Analyze the input and format and structure the output."""

"""
Main conversation event loop
"""


def main():
    api_key = (dotenv.dotenv_values()).get("OPENAI_API_KEY")
    traiage = OpenAIAssistant(
        filepath="/home/tikoehle/Downloads/", api_key=api_key, kwargs=traiage_args
    )
    conversation = ConversationFactory.create_assistant(traiage)
    while True:
        try:
            user = conversation.get_utf8_input(prompt="You> ")
            exec_time, answer = conversation.create(
                text=user, instructions=message_instructions
            )
            print(f"({exec_time})> {answer}")
            logger.info(f"Run steps:\n{conversation.log_run_steps()}")

        except KeyboardInterrupt:
            print("\nTerminated by the user.")
            break
    return 0


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="OpenAI Assistant API Client (type 'exit' or CTRL-C to end)."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose")
    parser.add_argument("-D", "--debug", action="store_true", help="more verbose")
    args = parser.parse_args()

    if args.debug:
        log_level = logging.DEBUG
    elif args.verbose:
        log_level = logging.INFO
    else:
        log_level = logging.ERROR

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s.%(msecs)03d %(name)-15s %(levelname)-6s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    main()
