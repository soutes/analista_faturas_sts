import json
import re
import shutil
import subprocess
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "prompts" / "system_prompt.md"
MCP_EMPTY = ROOT / ".mcp_empty.json"
LOG_PATH = ROOT / "data" / "agent.log"


class AgentError(RuntimeError):
    pass


def _log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)


def get_configured_model() -> str:
    try:
        config_path = Path.home() / ".claude.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            active_id = data.get("activeProviderProfileId")
            if active_id:
                for profile in data.get("providerProfiles", []):
                    if profile.get("id") == active_id:
                        model = profile.get("model", "Desconhecido")
                        provider = profile.get("name") or profile.get("provider", "Desconhecido")
                        return f"`{model}` via {provider}"
    except Exception:
        pass
    return "Modelo Padrão do OpenClaude"


def _find_claude_cli() -> str:
    cli = shutil.which("openclaude") or shutil.which("openclaude.cmd")
    if not cli:
        raise AgentError(
            "OpenClaude CLI não encontrado no PATH. "
            "Instale com: npm install -g openclaude"
        )
    return cli


def _build_user_message(invoice_text: str) -> str:
    return (
        "Analise a fatura abaixo e retorne SOMENTE o objeto JSON conforme o schema "
        "descrito nas instruções de sistema. Não escreva nada antes ou depois do JSON, "
        "nem use cercas markdown.\n\n"
        "## Texto da fatura\n\n"
        f"```\n{invoice_text}\n```"
    )


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return fence.group(1).strip() if fence else text


def call_claude(user_msg: str, model: str = "claude-3-7-sonnet-latest", timeout: int = 300) -> str:
    """Chama openclaude usando stdin para contornar bug do cmd.exe do Windows e evitar bloqueios de permissão do agente."""
    cli = _find_claude_cli()
    
    safe_prompt = "Analise o texto da fatura fornecido na entrada padrão (stdin) e responda apenas com o JSON conforme o system prompt."

    cmd = [
        cli,
        "-p", safe_prompt,
        "--append-system-prompt-file", str(PROMPT_PATH),
        "--strict-mcp-config",
        "--mcp-config", str(MCP_EMPTY),
        "--disable-slash-commands",
    ]

    _log(
        f"call_claude start | model={model} | "
        f"user_chars={len(user_msg)} (via stdin) | system_chars=file"
    )
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=user_msg,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=str(ROOT)
        )
    except subprocess.TimeoutExpired:
        _log(f"call_claude TIMEOUT após {timeout}s")
        raise AgentError(
            f"OpenClaude CLI não respondeu em {timeout}s. Verifique data/agent.log."
        )

    dt = time.time() - t0
    _log(
        f"call_claude end | rc={proc.returncode} | elapsed={dt:.1f}s | "
        f"stdout_chars={len(proc.stdout)} | stderr_chars={len(proc.stderr)}"
    )

    if proc.returncode != 0:
        error_msg = proc.stderr.strip()
        if not error_msg:
            error_msg = proc.stdout.strip()
        _log(f"error: {error_msg[:500]}")
        raise AgentError(
            f"OpenClaude CLI retornou erro {proc.returncode}: {error_msg[:500]}"
        )
    return proc.stdout.strip()


def analyze_invoice(invoice_text: str, model: str = "claude-3-7-sonnet-latest") -> dict:
    if not invoice_text or len(invoice_text) < 50:
        raise AgentError("Texto extraído da fatura está vazio ou curto demais.")

    user_msg = _build_user_message(invoice_text)
    raw = call_claude(user_msg, model=model)
    cleaned = _strip_json_fences(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        _log(f"JSON parse falhou: {exc} | first500={cleaned[:500]}")
        raise AgentError(
            f"Resposta do Claude não é JSON válido. Erro: {exc}. "
            f"Primeiros 500 chars: {cleaned[:500]}"
        ) from exc


def analyze_extrato_parcial(texto_ocr: str, model: str = "claude-3-7-sonnet-latest") -> dict:
    """Analisa texto OCR de prints do app do banco (extrato em aberto, não fatura final).
    OCR é menos confiável que PDF — instrui o agente a ignorar ruído e
    inferir transações com tolerância a erros de reconhecimento."""
    if not texto_ocr or len(texto_ocr) < 30:
        raise AgentError("Texto OCR muito curto ou vazio.")

    user_msg = (
        "Analise o texto abaixo, EXTRAÍDO POR OCR de prints do app de banco "
        "(extrato em aberto, ainda não é fatura fechada).\n\n"
        "## Formato típico desse app de banco\n\n"
        "O extrato lista múltiplos cartões. Cada cartão começa com um cabeçalho de separação "
        "e depois lista suas transações. Cada transação ocupa 2 linhas.\n\n"
        "Estrutura completa:\n"
        "  Final 9477   R$ 261,06          ← IGNORAR — cabeçalho do cartão 9477\n"
        "  15/03/2026   Parcela 3 de 04    ← linha 1 da transação: data + parcela\n"
        "  SHOPEE *SanJeroniArt   R$ 52,65 ← linha 2 da transação: estabelecimento + valor\n"
        "  10/03/2026   Parcela 3 de 03    ← linha 1 da próxima transação\n"
        "  PRIVALIA BRA*Priv   R$ 79,54    ← linha 2 da próxima transação\n"
        "  Final 7878   R$ 124,63          ← IGNORAR — cabeçalho do cartão 7878\n"
        "  07/05/2026                      ← linha 1 (sem parcela nesse caso)\n"
        "  MERCADOLIVRE*MERCAD   R$ 35,51  ← linha 2\n\n"
        "REGRA ABSOLUTA: qualquer linha que comece com 'Final' seguido de 4 dígitos "
        "é cabeçalho de cartão → DESCARTAR, nunca criar transação a partir dela.\n\n"
        "## Regras críticas\n\n"
        "1. NUNCA inclua como transação: cabeçalhos 'Final NNNN', saldos, limites disponíveis, "
        "pagamento mínimo, datas de vencimento ou qualquer linha sem valor monetário de compra.\n"
        "2. Para cada transação, associe corretamente: a data da linha 1 ao estabelecimento da linha 2. "
        "Ambos devem ir no mesmo objeto JSON.\n"
        "3. Créditos/estornos têm valor NEGATIVO (ex: '-R$ 75,14' → valor: -75.14). Inclua-os normalmente.\n"
        "4. EXTRAIA TODAS AS TRANSAÇÕES SEM PULAR NENHUMA, de todos os cartões listados.\n"
        "5. 'Parcela N de NN' → campo `parcela` no formato 'N/NN'.\n"
        "6. O campo `fatura.total` = soma líquida de todas as transações (débitos + créditos).\n"
        "7. Valores no Brasil usam vírgula decimal (R$ 1.234,56). Converta para float com ponto (1234.56).\n"
        "8. OCR pode ter ruído. Linhas idênticas (mesmo estabelecimento, data e valor) → inclua apenas uma.\n"
        "9. Para campos do bloco `fatura` que não puder inferir, use null.\n\n"
        "Retorne SOMENTE o JSON conforme o schema do system prompt, sem texto antes ou depois.\n\n"
        "## Texto OCR\n\n"
        f"```\n{texto_ocr}\n```"
    )
    raw = call_claude(user_msg, model=model)
    cleaned = _strip_json_fences(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        _log(f"JSON parse falhou (extrato): {exc} | first500={cleaned[:500]}")
        raise AgentError(
            f"Resposta do agente não é JSON válido. Erro: {exc}. "
            f"Primeiros 500 chars: {cleaned[:500]}"
        ) from exc
