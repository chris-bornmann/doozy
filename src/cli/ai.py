
import pathlib
import threading
from typing import Annotated, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
import typer
from prettytable import PrettyTable

from app.config import Settings
from routers.ai import parse_item_request, transcribe_audio

app = typer.Typer()


@app.command('request')
def ai_request(
    request: Annotated[str, typer.Argument(help="Natural language request, e.g. 'Create a new item called Buy milk'")],
):
    """Parse a natural language item request using Claude and print the result."""
    settings = Settings()
    if not settings.ANTHROPIC_API_KEY:
        typer.echo("Error: ANTHROPIC_API_KEY is not configured.", err=True)
        raise typer.Exit(code=1)

    try:
        parsed = parse_item_request(request, settings.ANTHROPIC_API_KEY)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Operation : {parsed.operation}")
    if parsed.item_id is not None:
        typer.echo(f"Item ID   : {parsed.item_id}")

    if parsed.fields:
        table = PrettyTable(["Field", "Value"])
        table.align["Field"] = "l"
        table.align["Value"] = "l"
        for key, value in parsed.fields.model_dump().items():
            if value is not None:
                table.add_row([key, value])
        if table.rows:
            typer.echo(table)

    if parsed.error:
        typer.echo(f"Error     : {parsed.error}", err=True)
        raise typer.Exit(code=1)


@app.command('voice')
def ai_voice(
    audio_file: Annotated[pathlib.Path, typer.Argument(help="Path to an audio file (webm, mp4, wav, m4a, …)")],
):
    """Transcribe an audio file and parse the result as a natural language item request."""
    settings = Settings()
    if not settings.OPENAI_API_KEY:
        typer.echo("Error: OPENAI_API_KEY is not configured.", err=True)
        raise typer.Exit(code=1)
    if not settings.ANTHROPIC_API_KEY:
        typer.echo("Error: ANTHROPIC_API_KEY is not configured.", err=True)
        raise typer.Exit(code=1)

    try:
        transcript = transcribe_audio(audio_file.read_bytes(), audio_file.name, settings.OPENAI_API_KEY)
    except Exception as exc:
        typer.echo(f"Transcription error: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Transcript : {transcript}")

    try:
        parsed = parse_item_request(transcript, settings.ANTHROPIC_API_KEY)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Operation : {parsed.operation}")
    if parsed.item_id is not None:
        typer.echo(f"Item ID   : {parsed.item_id}")

    if parsed.fields:
        table = PrettyTable(["Field", "Value"])
        table.align["Field"] = "l"
        table.align["Value"] = "l"
        for key, value in parsed.fields.model_dump().items():
            if value is not None:
                table.add_row([key, value])
        if table.rows:
            typer.echo(table)

    if parsed.filter:
        table = PrettyTable(["Filter", "Value"])
        table.align["Filter"] = "l"
        table.align["Value"] = "l"
        for key, value in parsed.filter.model_dump().items():
            if value is not None:
                table.add_row([key, value])
        if table.rows:
            typer.echo(table)

    if parsed.error:
        typer.echo(f"Error     : {parsed.error}", err=True)
        raise typer.Exit(code=1)


_DEFAULT_RECORDING_PATH = pathlib.Path("/tmp/doozy_recording.wav")
_SAMPLE_RATE = 16_000  # 16 kHz mono — optimal input format for Whisper


@app.command('record')
def ai_record(
    output: Annotated[
        pathlib.Path,
        typer.Option("--output", "-o", help="Path to write the recorded WAV file"),
    ] = _DEFAULT_RECORDING_PATH,
):
    """Record audio from the microphone and save it to a WAV file."""
    frames: list[np.ndarray] = []
    stop_event = threading.Event()

    def callback(indata: np.ndarray, _frame_count, _time, _status):
        if not stop_event.is_set():
            frames.append(indata.copy())

    with sd.InputStream(samplerate=_SAMPLE_RATE, channels=1, dtype="float32", callback=callback):
        typer.echo("Recording… press Enter to stop.")
        input()
        stop_event.set()

    audio = np.concatenate(frames, axis=0)
    sf.write(str(output), audio, _SAMPLE_RATE)
    duration = len(audio) / _SAMPLE_RATE
    typer.echo(f"Saved {duration:.1f}s to {output}")
