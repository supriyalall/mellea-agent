"""
Example use case for BeeAI integration: utilizing a Mellea program to write an email with an IVF loop.
"""
import os
import asyncio
import sys
import inspect
from typing import Annotated, Callable
from a2a.types import Message
from agentstack_sdk.a2a.types import AgentMessage
from agentstack_sdk.server import Server
from agentstack_sdk.a2a.extensions import (
    LLMServiceExtensionServer, LLMServiceExtensionSpec,
    TrajectoryExtensionServer, TrajectoryExtensionSpec,
    AgentDetail
)
from agentstack_sdk.a2a.extensions.ui.form import (
    FormExtensionServer, FormExtensionSpec, FormRender, TextField
)
from mellea import MelleaSession, start_session
from mellea.stdlib.base import ChatContext, ModelOutputThunk
from mellea.backends.openai import OpenAIBackend

from mellea.stdlib.sampling import RejectionSamplingStrategy
from mellea.stdlib.sampling.types import SamplingResult
from mellea.stdlib.sampling.base import Context
from mellea.stdlib.requirement import req, Requirement, simple_validate

def bee_app(func: Callable) -> Callable:
     """Serves as a wrapper that takes any Mellea program and converts it to a BeeAI Agent. This is an example for an email writer."""
     server = Server()

     params : dict = inspect.signature(func).parameters # Mapping params from Mellea function onto form inputs
     form_fields : list[str] = list(params.keys())[1:-1]
     all_fields : list[TextField] = []

     for field in form_fields:
         all_fields.append(TextField(id=field, label=field, col_span=2)) #Maps all input params from Mellea agent into BeeAI Forms

     form_render = FormRender(
                id="input_form",
                title="Please provide your information",
                columns=2,
                fields=all_fields
            )
     form_extension_spec = FormExtensionSpec(form_render)


     #@server.agent(name="Mellea Agent", detail=AgentDetail(interaction_mode="single-turn", author={"name": "Mellea Team"}, source_code_url="https://github.com/supriyalall/mellea/tree/main"), description="BeeAI Agent with Mellea backend")
     @server.agent()
     async def mellea_agent(input: Message,
                     llm: Annotated[LLMServiceExtensionServer, LLMServiceExtensionSpec.single_demand()],
                     trajectory: Annotated[TrajectoryExtensionServer, TrajectoryExtensionSpec()],
                     form: Annotated[FormExtensionServer,
                                     form_extension_spec]):
        """BeeAI Agent with Mellea Backend -- Email Writer Example"""
        
        form_data = form.parse_form_response(message=input)
        inputs = [form_data.values[key].value for key in form_data.values] # Extracting all of the user inputs from the form
        llm_config = llm.data.llm_fulfillments.get("default")

        for i in range(2): #Fixed loop budget to two iterations
            yield trajectory.trajectory_metadata(title=f"Attempt {i + 1}/2", content=f"Generating message...")
            m = MelleaSession(OpenAIBackend(
                model_id=llm_config.api_model,
                api_key=llm_config.api_key,
                base_url=llm_config.api_base
            ))

            sampling = await asyncio.to_thread(func, m, *inputs)

            validations = sampling.sample_validations[0]
            all_passed = all(bool(val_result) for _, val_result in validations)
            if all_passed:
                yield trajectory.trajectory_metadata(title=f"✓ Attempt {i + 1} succeeded!")
                yield AgentMessage(text=sampling.value)
                return

            status = "\n".join(f"{'✓' if bool(v) else '✗'} {getattr(r, 'description', str(r))}" for r, v in validations)
            yield trajectory.trajectory_metadata(title=f"✗ Attempt {i + 1} failed", content=status)

        yield AgentMessage(text=sampling.value)

     server.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 8000)))

     return wrapper




def main():
    # Mellea program shown below!
    @bee_app
    def mellea_func(m: MelleaSession, sender: str, recipient, subject: str, topic: str, sampling_iters : int = 3) -> tuple[ModelOutputThunk, Context] | SamplingResult:
        """
        Example email writing module that utilizes an IVR loop in Mellea to generate an email with a specific list of requirements.
        Inputs:
            sender: str
            recipient: str
            subject: str
            topic: str
	Output:
            sampling: tuple[ModelOutputThunk, Context] | SamplingResult
        """
        requirements = [
            req("Be formal."),
            req("Be funny."),
            req(f"Make sure that the email is from {sender}, is towards {recipient}, has {subject} as the subject, and is focused on {topic} as a topic"),
            Requirement("Use less than 100 words.",
            validation_fn=simple_validate(lambda o: len(o.split()) < 100))
	]
        sampling = m.instruct(f"Write an email from {sender}. Subject of email is {subject}. Name of recipient is {recipient}. Topic of email should be {topic}.", requirements=requirements, strategy=RejectionSamplingStrategy(loop_budget=1), return_sampling_results=True)

        return sampling

if __name__ == "__main__":
    main()
