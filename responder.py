import json
import logging
import secrets
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from jinja2.utils import select_autoescape
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from talbot.agents.models import AgentsResults, ResponderResults
from talbot.config import aws_config
from talbot.config import talbot_filesystem as fs
from talbot.config import talbot_filesystem_config as fs_config
from talbot.parsing.models import TicketParsed
from talbot.parsing.parse import run_parsing_pipeline

logger = logging.getLogger(__name__)


class SummarizerOutput(BaseModel):
    """Summarizer output."""

    summary: str


class ResponderOutput(BaseModel):
    """Responder output."""

    targeted_name: str
    response: str


class AgentInput(BaseModel):
    """Input schema for the agent workflow."""

    ticket_id: str
    skip_report: bool


class AgentState(BaseModel):
    """State schema for the agent workflow."""

    ticket_id: str
    skip_report: bool  # This can't be passed as context due to UiPath limiations
    ticket_parsed: TicketParsed
    agents_results: AgentsResults
    report: str | None = None
    summary: str | None = None
    response: str | None = None


class AgentOutput(BaseModel):
    """Output schema for the agent workflow."""

    report: str
    response: str
    summary: str


EXPECTED_REPORTS = []

COURTESY_LINES = [
    "Thank you for reaching out to us.",
    "I appreciate you taking the time to contact us.",
    "Thank you for bringing this to our attention.",
    "I hope this message finds you well.",
]

CLOSING_LINES = [
    "We appreciate your cooperation with our team. Please keep us posted on this matter.",
    "Our team is standing by to further assist you",
    "Looking forward to your update. Thank you in advance.",
    "Please let us know how things go - we're here to help.",
    "I'll keep an eye on this - please update us with any changes.",
]


class ResponderAgent:
    """Agent responsible for generating customer responses based on ticket analysis."""

    def __init__(self):
        self.chat_model = ChatBedrockConverse(**aws_config.models.responder.model_dump())

        self.chat_model_responder = self.chat_model.with_structured_output(ResponderOutput)
        self.chat_model_summarizer = self.chat_model.with_structured_output(SummarizerOutput)

        self.env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "prompts")), autoescape=select_autoescape()
        )
        self.responder_template = self.env.get_template("responder.jinja")

    @staticmethod
    def reporter_node(state: AgentState) -> AgentState:  # noqa: PLR0912
        """Generate a report from ticket findings and solutions.

        Args:
            state: The current agent state containing ticket information
        Returns:
            Dictionary containing the generated report
        """
        if state.skip_report:
            logger.info(f"Skipping reporter node for ticket {state.ticket_id}")
            return {"report": None}

        logger.info(f"Reporter node called for ticket {state.ticket_id}")
        with fs.open(f"{fs_config.tickets_solved}/{state.ticket_id}/agent_results.json", "r", encoding="utf-8") as f:
            agent_results = json.load(f)

            plan = f"# Ticket {state.ticket_id}\n\nHere are the crucial entities that agents is going to use:\n"

            plan += "- **Pops**:\n"
            for pop_location in agent_results["crucial_entities"]["popLocation"]:
                plan += f"- id: {pop_location['id']}, name: {pop_location['name']}\n"
            plan += "- **Sites**:\n"
            for site in agent_results["crucial_entities"]["site"]:
                plan += f"- id: {site['entity']['id']}, name: {site['entity']['name']}\n"
            plan += "- **NetworkInterfaces**:\n"
            for network_interface in agent_results["crucial_entities"]["networkInterface"]:
                plan += f"- id: {network_interface['entity']['id']}, name: {network_interface['entity']['name']}\n"
            plan += "- **AllocatedIPs**:\n"
            for allocated_ip in agent_results["crucial_entities"]["allocatedIP"]:
                plan += f"- id: {allocated_ip['entity']['id']}, name: {allocated_ip['entity']['name']}\n"
            plan += "- **TimeFrames**:\n"
            for time_frame in agent_results["crucial_entities"]["timeFrame"]:
                plan += f"- {time_frame}\n"
            plan += "- **TimeZones**:\n"
            for timezone in agent_results["crucial_entities"]["timezone"]:
                plan += f"- {timezone}\n"
            plan += "\n"

            plan += (
                "Here is a detailed plan that support engineer could execute. Links lead to supporting KB articles:\n"
            )
            for action in agent_results["reranked_actions"].values():
                plan += f"## {' '.join(action['name'].split('_'))}\n"
                if "kb_correlation" in action and action["kb_correlation"]:
                    for kb_action in action["kb_correlation"]:
                        name, title, url = kb_action["subaction"], kb_action["article_title"], kb_action["article_url"]
                        name = " ".join(name.split("_"))
                        plan += f"- **{name}**: [{title}]({url})\n"
                else:
                    for subaction in action["actions"]:
                        name = " ".join(subaction.split("_"))
                        plan += f"- **{name}**\n"

            report = "## Here is the report from actions executed by the agents:\n\n"
            if "timezone_talbot" in agent_results["crucial_entities"]:
                report += "**Assumed Timezone:** " + agent_results["crucial_entities"]["timezone_talbot"] + "\n\n"
                report += (
                    "**Assumed TimeFrames:** " + ", ".join(agent_results["crucial_entities"]["timeFrame_talbot"]) + "\n"
                )
            else:
                report += "**Assumed Timezone:** No timezone was detected.\n\n"

            report += "\n--------------------------------\n"
            for task, execution in zip(agent_results["plan"], agent_results["executions"], strict=False):
                # report += f"## Task 1\n\n {task}\n\n"
                if execution == "Error":
                    report += f"### Task ended with error during execution\n\n task: {task}\n\n"
                    continue
                execution_json = json.loads(execution)
                report += f"### What:\n\n {execution_json['what']}\n\n"
                report += f"### Evidence:\n\n {execution_json['evidence']}\n\n"
                report += f"### Conclusion:\n\n {execution_json['conclusion']}\n\n"
                report += "\n--------------------------------\n"

        return {"report": report}

    def responder_node(self, state: AgentState) -> AgentState:
        """Responder node."""
        prompt = self.env.get_template("report_summarizer.jinja").render(REPORT=state.ticket_parsed.parsed)
        summary = self.chat_model_summarizer.invoke([SystemMessage(content=prompt)]).summary
        logger.info(f"Summary: {summary}")

        responder_prompt = self.responder_template.render(
            ESCALATED=False,
            EMAILS=state.ticket_parsed.external_requesters,
            SUMMARY=summary,
        )
        response = self.chat_model_responder.invoke([SystemMessage(content=responder_prompt)])

        response = f"""
# Ticket {state.ticket_id}

Hi {response.targeted_name},

{secrets.choice(COURTESY_LINES)}

{response.response}

{secrets.choice(CLOSING_LINES)}
        """
        logger.info(f"Response: {response}")
        return {"response": response, "summary": summary}

    @staticmethod
    def save_results(state: AgentState) -> AgentOutput:
        """Save results node."""
        state.agents_results.responder_results = ResponderResults(
            report=state.report, response=state.response, summary=state.summary
        )
        with fs.open(f"{fs_config.tickets}/{state.ticket_id}/agents_results.json", "w", encoding="utf-8") as f:
            f.write(state.agents_results.model_dump_json(indent=2))

        return {
            "report": state.report,
            "response": state.response,
            "summary": state.summary,
        }

    @staticmethod
    def init_agent(state: AgentInput) -> AgentState:
        """Initialize the agent state."""
        run_parsing_pipeline(state.ticket_id)
        with fs.open(f"{fs_config.tickets}/{state.ticket_id}/parsed.json", "r", encoding="utf-8") as f:
            parsed_input = TicketParsed.model_validate_json(f.read())

        try:
            with fs.open(f"{fs_config.tickets}/{state.ticket_id}/agents_results.json", "r", encoding="utf-8") as f:
                agent_results = AgentsResults.model_validate_json(f.read())
        except FileNotFoundError:
            agent_results = AgentsResults()

        return {
            "ticket_id": state.ticket_id,
            "skip_report": state.skip_report,
            "ticket_parsed": parsed_input,
            "agents_results": agent_results,
        }

    def create_agent_graph(self) -> CompiledStateGraph:
        """Create and return the LangGraph agent workflow."""
        workflow = StateGraph(AgentState, input=AgentInput, output=AgentOutput)
        workflow.add_node("init_agent", self.init_agent)
        workflow.add_node("reporter", self.reporter_node)
        workflow.add_node("responder", self.responder_node)
        workflow.add_node("save_results", ResponderAgent.save_results)

        workflow.set_entry_point("init_agent")
        workflow.add_edge("init_agent", "reporter")
        workflow.add_edge("reporter", "responder")
        workflow.add_edge("responder", "save_results")
        workflow.add_edge("save_results", END)

        return workflow.compile()
