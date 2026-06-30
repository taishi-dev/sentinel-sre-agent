from collections.abc import Callable

from sentinel.domain import Diagnosis, Incident
from sentinel.parsing import parse_diagnosis
from sentinel.prompting import build_diagnosis_prompt
from sentinel.telemetry import TelemetryProvider

# A generate function maps a prompt to the model's raw JSON text response.
GenerateFn = Callable[[str], str]

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiDiagnoser:
    """Diagnoser adapter. Pure orchestration: the SDK lives in `vertex_generate`.

    Build the prompt from telemetry, ask the model for strict JSON, and parse it
    through the fail-toward-escalation parser. Inject a fake `generate` to test
    offline; inject `vertex_generate(...)` for live Gemini calls.
    """

    def __init__(self, generate: GenerateFn) -> None:
        self._generate = generate

    def diagnose(self, incident: Incident, telemetry: TelemetryProvider) -> Diagnosis:
        snapshot = telemetry.snapshot(incident.service)
        prompt = build_diagnosis_prompt(incident, snapshot)
        raw = self._generate(prompt)
        return parse_diagnosis(raw)


def vertex_generate(
    project: str,
    location: str,
    model: str = DEFAULT_MODEL,
) -> GenerateFn:
    """Build a live generate function backed by Gemini on Vertex AI via ADC."""
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=project, location=location)

    def generate(prompt: str) -> str:
        # google-genai's generate_content has a partially-unknown `contents` union
        # (an unresolved member type in the SDK); scope the suppression to this call.
        response = client.models.generate_content(  # pyright: ignore[reportUnknownMemberType]
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Diagnosis,
                temperature=0.0,
            ),
        )
        return response.text or ""

    return generate
