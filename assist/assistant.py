"""
Implements the OpenAI Assistants API (Beta).
https://platform.openai.com/docs/assistants/overview

Dec 2023, Timo Koehler
"""

import sys
import time
import json
import dotenv
import logging
from pathlib import Path
from openai import OpenAI
from tools.functioncalling import Functions

logger = logging.getLogger(__name__)


class OpenAIAssistant:
    """Create an assistant in the OpenAI API."""

    def __init__(self, filepath, api_key, kwargs):
        self.api_key = api_key
        self.kwargs = kwargs
        self.name = self.kwargs.get("name")
        self.instructions = self.kwargs.get("instructions")
        self.model = self.kwargs.get("model")
        self.tools = self.kwargs.get("tools", [])
        self.files = self.kwargs.get("files", [])
        self.file_download_path = Path(filepath)
        self.file_ids = []
        self.assistant_id = None
        self.thread = None
        logger.info("%s initialized", self.__class__.__name__)

        if self.api_key is None:
            print(
                """No OpenAI API key. Create a local .env file
                which contains the OPENAI_API_KEY='...'."""
            )
            sys.exit(1)

    def get_utf8_input(self, prompt):
        try:
            text = input(prompt).encode("utf-8").decode("utf-8")
            if text.lower() == "exit":
                print("Ending the conversation.")
                sys.exit(0)
        except UnicodeDecodeError:
            print("Invalid UTF-8 encoding. Please enter valid UTF-8 text. Exiting.")
            sys.exit(1)
        return text

    def select_assistant(self):
        """Choose an existing assistant-id from the list."""
        ids = {}
        sel = 0
        self.file_list()
        print("Existing assistants: ", end="")
        for i, assistant in enumerate(self.client.beta.assistants.list()):
            ids[i] = assistant.id
            print(
                f"""\n#{i}: {assistant.id}
                Model: {assistant.model}
                Name: {assistant.name}
                Files: {assistant.file_ids}
                Instructions: {assistant.instructions}"""
            )
        if len(ids) > 0:
            while True:
                try:
                    sel = self.get_utf8_input(
                        prompt=f"Select assistant [0..{i}] or create a new one [c]: "
                    )
                    if sel.isdigit() and int(sel) <= i:
                        self.assistant_id = ids.get(int(sel))
                        logger.info("Selected assistant-id %s", ids.get(int(sel)))
                        break
                    elif sel.lower() == "c":
                        logger.info("Creating a new assistant")
                        break
                except KeyboardInterrupt:
                    print("\nTerminated.")
                    sys.exit(1)
        else:
            print("None")

    def file_list(self):
        """List uploaded files."""
        for i, file in enumerate(self.client.files.list()):
            logger.info("File object %s: '%s' %s", i, file.id, file.filename)

    def assistant_file_upload(self):
        """Upload files to the storage space."""
        file_lst = []
        for filepath in self.files:
            file_lst.append(
                self.client.files.create(
                    file=open(Path(filepath), "rb"), purpose="assistants"
                )
            )
        self.file_ids = [file.id for file in file_lst]
        logger.info("File objects for upload: %s", self.file_ids)

    def file_download(self, file_name, output_file_path):
        """File download from annotation."""
        image_data = self.client.files.content(file_name)
        image_data_bytes = image_data.read()
        with open(output_file_path, "wb") as file:
            file.write(image_data_bytes)

    def create_assistant_env(self):
        """In this order: ASSISTANT_ID in .env, assistant exists, create new one."""
        self.assistant_id = (dotenv.dotenv_values()).get("ASSISTANT_ID")
        if self.assistant_id is None:
            self.select_assistant()
            if self.assistant_id is None:
                if self.name and self.instructions and self.model and self.tools:
                    self.assistant_file_upload()
                    if len(self.file_ids) > 0:
                        assistant = self.client.beta.assistants.create(
                            name=self.name,
                            instructions=self.instructions,
                            model=self.model,
                            tools=self.tools,
                            file_ids=self.file_ids,
                        )
                        self.assistant_id = assistant.id
                    else:
                        assistant = self.client.beta.assistants.create(
                            name=self.name,
                            instructions=self.instructions,
                            model=self.model,
                            tools=self.tools,
                        )
                        self.assistant_id = assistant.id
                    print(f"Created assistant {self.assistant_id}")
        assert self.assistant_id is not None, "assistant_id is not initialized"


class Conversation(OpenAIAssistant):
    """Create a new conversation with existing assistant."""

    def __init__(self, filepath, api_key, **kwargs):
        super().__init__(filepath, api_key, kwargs)
        self.client = OpenAI(api_key=self.api_key)
        self.create_assistant_env()
        self.thread = self.client.beta.threads.create()
        self.thread_instructions = None
        logger.info("%s initialized", self.__class__.__name__)

    def create(self, text, instructions=None):
        """Create a conversation Thread in the assistants API."""
        answer = None
        start = time.time()
        self.thread_instructions = instructions
        self.message = self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=text,
            # TODO: Add file on thread level.
            # self.file_ids = [file.id]
        )
        answer = self._dispatch()
        exec_time = time.strftime("%H:%M:%S", time.gmtime(time.time() - start))
        return exec_time, answer

    def _dispatch(self):
        """Assistant read the conversation Thread and decide whether
        to call tools (if enabled) or return an answer."""
        answer = None
        self.run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant_id,
            instructions=self.thread_instructions
            # TODO: Attach tools to the thread.
            # tools=[{"type": "code_interpreter"}, {"type": "retrieval"}]
        )
        while True:
            run_status = self.wait_on_assistant()
            if run_status == "requires_action":
                self.function_calling()
            elif run_status == "completed":
                answer = self.assistant_answer()
                break
            else:
                logger.warning("A new API run status has appeared: %s", run_status)
        return answer

    def _run_status(self):
        """Retrieve the assistant run status."""
        self.run = self.client.beta.threads.runs.retrieve(
            thread_id=self.thread.id, run_id=self.run.id
        )
        return self.run.status

    def wait_on_assistant(self):
        """Block until the assistant is ready for work."""
        status = self._run_status()
        while status == "queued" or status == "in_progress":
            status = self._run_status()
            time.sleep(0.2)
        return self.run.status

    def function_calling(self):
        """Intelligently return the functions that need to be called
        along with their arguments."""
        tool_outputs = []
        tool_calls = self.run.required_action.submit_tool_outputs.tool_calls
        print(f"Assistant requests {len(tool_calls)} tools.")
        for tool_call in self.run.required_action.submit_tool_outputs.tool_calls:
            output = '{"empty": "empty"}'
            tool_call_id = tool_call.id
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            logger.info("Assistant requested %s(%s)", name, arguments)

            try:
                output = getattr(Functions, name)(**arguments)
                tool_outputs.append(
                    {"tool_call_id": tool_call_id, "output": json.dumps(output)}
                )
            except AttributeError:
                logger.error(f"The assistant called a non-existent function '{name}'.")

            logger.info("Function call returning: %s", output)
        self.run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id, run_id=self.run.id, tool_outputs=tool_outputs
        )

    def assistant_answer(self):
        """Assistant generated answer after the last user message."""
        answer = []
        completed_message = self.client.beta.threads.messages.list(
            thread_id=self.thread.id, order="asc", after=self.message.id
        )

        # Message annotations
        for m in completed_message:
            message_content = m.content[0].text
            annotations = message_content.annotations
            citations = []

            for index, annotation in enumerate(annotations):
                # Replace the text with a footnote
                message_content.value = message_content.value.replace(
                    annotation.text, f" [{index}]"
                )

                # Gather citations based on annotation attributes
                if file_citation := getattr(annotation, "file_citation", None):
                    cited_file = self.client.files.retrieve(file_citation.file_id)
                    citations.append(
                        f"[{index}] {file_citation.quote} from {cited_file.filename}"
                    )
                elif file_path := getattr(annotation, "file_path", None):
                    cited_file = self.client.files.retrieve(file_path.file_id)
                    citations.append(
                        f"[{index}] {cited_file.filename} {self.file_download_path}"
                    )
                    # File download
                    fname = Path(cited_file.filename).name
                    fpath = self.file_download_path.joinpath(fname)
                    print(f"Requested file {fname} download to {fpath}")
                    logger.info("Assistant file download %s %s", fname, fpath)
                    self.file_download(fname, fpath)

        if citations:
            # Add footnotes to the end of the message before displaying to user
            message_content.value += "\n" + "\n".join(citations)

        answer.append(m.content[0].text.value)
        return "\n".join(answer)

    def log_run_steps(self):
        """Logs the run steps of the current message."""
        log = []
        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=self.thread.id, run_id=self.run.id
        )
        for i in run_steps.data:
            log.append(
                json.dumps(json.loads(i.step_details.model_dump_json()), indent=2)
            )
        return "".join(log)


class ConversationFactory:
    """Create conversation(s) with existing OpenAI assistant(s)."""

    @staticmethod
    def create_assistant(assistant_instance):
        filepath = assistant_instance.file_download_path
        api_key = assistant_instance.api_key
        kwargs = assistant_instance.kwargs
        return Conversation(filepath, api_key=api_key, **kwargs)


if __name__ == "__main__":
    pass
