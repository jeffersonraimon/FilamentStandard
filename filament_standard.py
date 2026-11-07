# /// script
# requires-python = ">=3.12"
# dependencies = []
#
# [tool.orcaslicer.plugin]
# id = "filament-standard"
# name = "FilamentStandard"
# description = "Keep a standard filament list (order, per-nozzle presets and colours) for your printers, restore it after opening projects, and sync spools and prices from Spoolman. English / Português."
# author = "Jefferson J. Raimon"
# version = "3.0.0"
# ///
"""FilamentStandard - an OrcaSlicer plugin.

OrcaSlicer keeps one filament list per printer profile and replaces it whenever a
.3mf project is opened, so the order and colours of your filaments drift from
printer to printer and nozzle to nozzle. FilamentStandard keeps one *standard* list - slot -> filament preset per
nozzle diameter, colour, Spoolman spool - and offers:

* Capture the current project's list as the standard.
* Restore presets now: re-assign the presets of the existing slots live through
  ``orca.host.preset.filament.begin_update(slot, name)``. The host API cannot
  add slots or change project colours.
* Apply prices: write each preset's price per kg as an unsaved edit, through the
  same API.
* Spoolman sync (optional, asks before the first connection): new / removed
  spools, colours and the average price per preset, previewed before anything
  changes. Read-only: the plugin only GETs the spool list.
* Optional (off by default): restore the presets whenever a New project starts.

Two editions are built from this file. The Orca Cloud edition uses only the plugin
API and the plugin's own storage folder.
>>> full-edition
The full edition (GitHub) adds an opt-in full restore that edits OrcaSlicer.conf
with OrcaSlicer closed (slot count and colours, which the API cannot change), run
by a detached helper: ``python filament_standard.py --apply <job.json>``, plus
``--restore <data dir> <standard.json>`` and ``--undo <data dir> <backup>``.
<<< full-edition
"""
from __future__ import annotations

import colorsys

# >>> full-edition
import datetime
import hashlib

# <<< full-edition
import json
import math
import os
import re

# >>> full-edition
import shutil
import subprocess

# <<< full-edition
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request

try:
    import orca  # only available inside OrcaSlicer
except ImportError:  # tests and the stand-alone helper
    orca = None

VERSION = "3.0.0"
# "full" (GitHub) or "cloud" (Orca Cloud): scripts/build_release.py removes the full-only blocks
EDITION = "full"
STD_FILE = "standard.json"
JOB_FILE = "job.json"
LOG_FILE = "apply.log"
DEFAULT_VARIANT = "default"
# OrcaSlicer adds a minimum purge to the colour-based volume. 92 mm³ reproduces the matrices
# OrcaSlicer 2.5 writes for the Bambu Lab A1; recalculating in the GUI refines it per printer.
FLUSH_OFFSET = 92
FLUSH_MAX = 900
LEGACY_DIRS = ("filamentos_padrao",)
ICON_FILE = "tab-icon.svg"
# 20 px tab icon in OrcaSlicer's style (white strokes on the dark tab bar); same as assets/tab-icon.svg
TAB_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20"><g fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round"><circle cx="4" cy="4.5" r="2.5"/><circle cx="4" cy="10" r="2.5" fill="#fff"/><circle cx="4" cy="15.5" r="2.5"/><path d="M8.5 4.5h9M8.5 10h9M8.5 15.5h5.5"/><path d="M16 13.5l2 2-2 2"/></g></svg>'
  # storage folders of the pre-2.0 Portuguese-only plugin

# ---------------------------------------------------------------- translations
STRINGS = {
    "en": {
        "title": "Filament standard",
        "current": "Current printer: {machine} ({nozzle} mm) - {n} slot(s) in the project",
        "actions": "Actions",
        "restore_live": "Restore presets now",
        "restore_live_tip": "Re-assigns the presets of the existing slots (cannot change colours or the number of slots)",
        # >>> full-edition
        "restore_full": "Full restore on close",
        # <<< full-edition
        # >>> full-edition
        "restore_full_tip": "When OrcaSlicer closes, writes the list, colours and prices into every selected printer",
        # <<< full-edition
        # >>> full-edition
        "relaunch": "reopen OrcaSlicer afterwards",
        # <<< full-edition
        # >>> full-edition
        "cancel_full": "Cancel scheduled restore",
        # <<< full-edition
        "capture": "Use current list as standard",
        "capture_tip": "Replaces the standard with the filaments and colours of the current project",
        "capture_confirm": "Replace the standard list with the filaments and colours of the current project?",
        "sync": "Sync with Spoolman",
        "apply_prices": "Apply prices to presets",
        "apply_prices_tip": "Writes each preset's price per kg (filament cost) as an unsaved edit; save the presets in OrcaSlicer to keep it",
        "msg_prices_running": "Applying the price of {n} preset(s)...",
        "msg_prices_done": "Price applied to {n} preset(s) as unsaved edits. Save the filament presets in OrcaSlicer to keep them.",
        "msg_prices_none": "No preset in the current project has a different price.",
        "spoolman_confirm": "Connect to Spoolman at {url}? The plugin only reads the spool list (filament, colour, price); nothing is sent.",
        "err_spoolman_consent": "Allow the connection to Spoolman first (press Sync with Spoolman and confirm).",
        "auto": "restore presets on New project",
        "standard": "Standard list",
        "col_color": "Colour",
        "col_variant_default": "Preset (default)",
        "col_variant": "Preset {nozzle} mm",
        "col_spool": "Spool",
        "col_project": "Current project",
        "add_slot": "Add slot",
        "save": "Save standard",
        "printers": "Printer profiles",
        "printers_help": "Printer profiles that use this standard. Presets are chosen by nozzle: the {nozzle} mm column if filled, otherwise the default column.",
        "add_current_printer": "Add current printer",
        "filter": "filter",
        "nozzle": "nozzle",
        "settings": "Settings",
        "spoolman_url": "Spoolman URL",
        "spoolman_help": "Leave empty to disable. Example: http://192.168.1.10:7912",
        "language": "Language",
        "lang_auto": "automatic",
        "sort_on_sync": "sort the list on Spoolman sync (PLA white, PLA black, other PLA, PETG white, PETG black, ...)",
        "reset": "Reset everything",
        "reset_confirm": "Erase the standard list and settings?",
        "json": "Import / export (JSON)",
        "json_export": "Show JSON",
        "json_import": "Import JSON",
        "sync_title": "Spoolman sync preview",
        "sync_added": "New slots",
        "sync_removed": "Removed slots (spool archived or deleted)",
        "sync_recolored": "Colour changes",
        "sync_prices": "Prices (average of the spools, per kg)",
        "sync_unmapped": "Spools without a preset",
        "sync_unmapped_help": "Pick the preset for each filament once; it is remembered for the next syncs.",
        "sync_apply": "Apply to standard",
        "sync_discard": "Discard",
        "none": "none",
        "spool_n": "spool {id}",
        "ok": "ok",
        "first_run": "No standard yet. Set up the list below or use \"Use current list as standard\".",
        "migrated": "Imported the standard from a previous install of the plugin ({n} slots). The Spoolman URL and the full restore were not carried over: set them again in Settings if you use them.",
        # >>> full-edition
        "full_section": "Full restore",
        # <<< full-edition
        # >>> full-edition
        "allow_conf_edit": "allow the full restore to edit OrcaSlicer.conf",
        # <<< full-edition
        # >>> full-edition
        "allow_conf_edit_help": "The plugin API cannot add slots or change colours, so the full restore edits OrcaSlicer.conf with OrcaSlicer closed. Only the filament lists of the selected printer profiles change; other settings in that file, such as printer access codes, are left as they are and are not copied. The backup keeps only the lists that change (undo: python filament_standard.py --undo <data dir> <backup folder>).",
        # <<< full-edition
        # >>> full-edition
        "full_confirm": "Schedule the full restore? When OrcaSlicer closes, the filament lists of the selected printer profiles in OrcaSlicer.conf will be replaced.",
        # <<< full-edition
        # >>> full-edition
        "err_conf_edit_off": "The full restore is off. Turn it on under Full restore.",
        # <<< full-edition
        "msg_saved": "Standard saved ({n} slots).",
        "msg_captured": "Current list ({n} slots, {machine}) saved as standard in the \"{column}\" column. Check the other columns.",
        "msg_live_none": "The {n} slots already use the standard presets.",
        "msg_live_running": "Updating {n} slot(s)...",
        "msg_live_done": "{n} slot(s) updated.",
        "msg_count_differs": "The project has {cur} slots and the standard {std}: the number of slots and the colours only change with the full restore.",
        # >>> full-edition
        "msg_full_scheduled": "Restore scheduled. Close OrcaSlicer: the list will be written to {n} printer profile(s) and OrcaSlicer will {after}.",
        # <<< full-edition
        # >>> full-edition
        "msg_after_reopen": "reopen by itself",
        # <<< full-edition
        # >>> full-edition
        "msg_after_closed": "stay closed",
        # <<< full-edition
        # >>> full-edition
        "msg_full_cancelled": "Scheduled restore cancelled (the helper exits without changing anything).",
        # <<< full-edition
        "msg_sync": "Spoolman: {spools} active spools. {added} new, {removed} removed, {recolored} colour change(s), {prices} price change(s), {unmapped} without a preset.",
        "msg_sync_applied": "Standard updated from Spoolman ({n} slots). Prices reach the presets on the next full restore.",
        "msg_reset": "Everything was reset.",
        "msg_imported": "JSON imported ({n} slots).",
        "err_busy": "A restore is already running",
        "err_empty": "The list needs at least one slot",
        "err_no_current": "Could not read the filaments of the current project",
        # >>> full-edition
        "err_no_python": "Python was not found. The full restore needs a Python 3 interpreter on PATH (or run the --restore command with OrcaSlicer closed).",
        # <<< full-edition
        # >>> full-edition
        "err_no_printers": "Select at least one printer profile first",
        # <<< full-edition
        "err_no_spoolman": "Set the Spoolman URL in Settings first",
        "err_preview_first": "Create the sync preview first",
        "err_bad_json": "Invalid JSON: {error}",
        "err_unknown": "unknown command: {cmd}",
    },
    "pt": {
        "title": "Filamentos padrão",
        "current": "Impressora atual: {machine} ({nozzle} mm) - {n} slot(s) no projeto",
        "actions": "Ações",
        "restore_live": "Restaurar perfis agora",
        "restore_live_tip": "Troca os perfis dos slots existentes (não muda cores nem a quantidade de slots)",
        # >>> full-edition
        "restore_full": "Restauração completa ao fechar",
        # <<< full-edition
        # >>> full-edition
        "restore_full_tip": "Quando o OrcaSlicer fechar, grava lista, cores e preços em todas as impressoras selecionadas",
        # <<< full-edition
        # >>> full-edition
        "relaunch": "reabrir o OrcaSlicer depois",
        # <<< full-edition
        # >>> full-edition
        "cancel_full": "Cancelar restauração agendada",
        # <<< full-edition
        "capture": "Usar a lista atual como padrão",
        "capture_tip": "Substitui o padrão pelos filamentos e cores do projeto atual",
        "capture_confirm": "Substituir a lista padrão pelos filamentos e cores do projeto atual?",
        "sync": "Sincronizar com o Spoolman",
        "apply_prices": "Aplicar preços aos perfis",
        "apply_prices_tip": "Grava o preço por kg (custo do filamento) de cada perfil como edição não salva; salve os perfis no OrcaSlicer para manter",
        "msg_prices_running": "Aplicando o preço de {n} perfil(is)...",
        "msg_prices_done": "Preço aplicado a {n} perfil(is) como edição não salva. Salve os perfis de filamento no OrcaSlicer para manter.",
        "msg_prices_none": "Nenhum perfil do projeto atual tem preço diferente.",
        "spoolman_confirm": "Conectar ao Spoolman em {url}? O plugin só lê a lista de carretéis (filamento, cor, preço); nada é enviado.",
        "err_spoolman_consent": "Permita antes a conexão com o Spoolman (clique em Sincronizar com o Spoolman e confirme).",
        "auto": "restaurar perfis ao criar Novo projeto",
        "standard": "Lista padrão",
        "col_color": "Cor",
        "col_variant_default": "Perfil (padrão)",
        "col_variant": "Perfil {nozzle} mm",
        "col_spool": "Carretel",
        "col_project": "Projeto atual",
        "add_slot": "Adicionar slot",
        "save": "Salvar padrão",
        "printers": "Perfis de impressora",
        "printers_help": "Perfis de impressora que usam este padrão. O perfil de filamento é escolhido pelo bico: a coluna {nozzle} mm se preenchida, senão a coluna padrão.",
        "add_current_printer": "Adicionar impressora atual",
        "filter": "filtrar",
        "nozzle": "bico",
        "settings": "Configuração",
        "spoolman_url": "URL do Spoolman",
        "spoolman_help": "Deixe vazio para desativar. Exemplo: http://192.168.1.10:7912",
        "language": "Idioma",
        "lang_auto": "automático",
        "sort_on_sync": "ordenar a lista ao sincronizar (PLA branco, PLA preto, demais PLA, PETG branco, PETG preto, ...)",
        "reset": "Apagar tudo",
        "reset_confirm": "Apagar a lista padrão e as configurações?",
        "json": "Importar / exportar (JSON)",
        "json_export": "Mostrar JSON",
        "json_import": "Importar JSON",
        "sync_title": "Prévia da sincronização com o Spoolman",
        "sync_added": "Slots novos",
        "sync_removed": "Slots removidos (carretel arquivado ou apagado)",
        "sync_recolored": "Cores alteradas",
        "sync_prices": "Preços (média dos carretéis, por kg)",
        "sync_unmapped": "Carretéis sem perfil",
        "sync_unmapped_help": "Escolha o perfil de cada filamento uma vez; ele fica salvo para as próximas sincronizações.",
        "sync_apply": "Aplicar ao padrão",
        "sync_discard": "Descartar",
        "none": "nenhum",
        "spool_n": "carretel {id}",
        "ok": "ok",
        "first_run": "Ainda não há padrão. Monte a lista abaixo ou use \"Usar a lista atual como padrão\".",
        "migrated": "Padrão importado de uma instalação anterior do plugin ({n} slots). A URL do Spoolman e a restauração completa não foram trazidas: configure de novo se usar.",
        # >>> full-edition
        "full_section": "Restauração completa",
        # <<< full-edition
        # >>> full-edition
        "allow_conf_edit": "permitir que a restauração completa edite o OrcaSlicer.conf",
        # <<< full-edition
        # >>> full-edition
        "allow_conf_edit_help": "A API de plugins não cria slots nem muda cores, então a restauração completa edita o OrcaSlicer.conf com o OrcaSlicer fechado. Só mudam as listas de filamentos dos perfis de impressora escolhidos; as outras configurações do arquivo, como os códigos de acesso das impressoras, ficam como estão e não são copiadas. O backup guarda só as listas alteradas (desfazer: python filament_standard.py --undo <pasta de dados> <pasta do backup>).",
        # <<< full-edition
        # >>> full-edition
        "full_confirm": "Agendar a restauração completa? Quando o OrcaSlicer fechar, as listas de filamentos dos perfis de impressora escolhidos no OrcaSlicer.conf serão substituídas.",
        # <<< full-edition
        # >>> full-edition
        "err_conf_edit_off": "A restauração completa está desligada. Ligue em Restauração completa.",
        # <<< full-edition
        "msg_saved": "Padrão salvo ({n} slots).",
        "msg_captured": "Lista atual ({n} slots, {machine}) salva como padrão na coluna \"{column}\". Confira as outras colunas.",
        "msg_live_none": "Os {n} slots já estão com os perfis do padrão.",
        "msg_live_running": "Ajustando {n} slot(s)...",
        "msg_live_done": "{n} slot(s) ajustado(s).",
        "msg_count_differs": "O projeto tem {cur} slots e o padrão {std}: a quantidade de slots e as cores só mudam com a restauração completa.",
        # >>> full-edition
        "msg_full_scheduled": "Restauração agendada. Feche o OrcaSlicer: a lista será gravada em {n} perfil(is) de impressora e o OrcaSlicer {after}.",
        # <<< full-edition
        # >>> full-edition
        "msg_after_reopen": "reabrirá sozinho",
        # <<< full-edition
        # >>> full-edition
        "msg_after_closed": "ficará fechado",
        # <<< full-edition
        # >>> full-edition
        "msg_full_cancelled": "Restauração agendada cancelada (o auxiliar encerra sem alterar nada).",
        # <<< full-edition
        "msg_sync": "Spoolman: {spools} carretéis ativos. {added} novo(s), {removed} removido(s), {recolored} cor(es) alterada(s), {prices} preço(s) alterado(s), {unmapped} sem perfil.",
        "msg_sync_applied": "Padrão atualizado pelo Spoolman ({n} slots). Os preços vão para os perfis na próxima restauração completa.",
        "msg_reset": "Tudo foi apagado.",
        "msg_imported": "JSON importado ({n} slots).",
        "err_busy": "Já existe uma restauração em andamento",
        "err_empty": "A lista precisa de pelo menos um slot",
        "err_no_current": "Não consegui ler os filamentos do projeto atual",
        # >>> full-edition
        "err_no_python": "Python não encontrado. A restauração completa precisa de um Python 3 no PATH (ou rode o comando --restore com o OrcaSlicer fechado).",
        # <<< full-edition
        # >>> full-edition
        "err_no_printers": "Selecione pelo menos um perfil de impressora antes",
        # <<< full-edition
        "err_no_spoolman": "Configure a URL do Spoolman antes",
        "err_preview_first": "Gere a prévia da sincronização primeiro",
        "err_bad_json": "JSON inválido: {error}",
        "err_unknown": "comando desconhecido: {cmd}",
    },
}
LANGUAGES = ("en", "pt")


def language_for(code):
    """'pt_BR', 'pt-PT', 'pt' -> 'pt'; everything else -> 'en'."""
    return "pt" if str(code or "").lower().replace("-", "_").startswith("pt") else "en"


def tr(lang, key, **kwargs):
    text = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key) or key
    return text.format(**kwargs) if kwargs else text


# ---------------------------------------------------------------- data model
def empty_standard():
    return {
        "version": 2,
        "slots": [],  # {"presets": {"default": name, "0.2": name}, "color": "#RRGGBB", "spool": int|None}
        "printers": {},  # printer profile name -> nozzle diameter ("0.4")
        "spool_map": {},  # "Vendor|Filament name" -> {"default": name, "0.2": name}
        "prices": {},  # filament preset name -> price per kg
        "spoolman_url": "",
        "spoolman_consent": "",  # origin the user allowed; the plugin connects only to it
        "auto_new_project": False,
        # >>> full-edition
        "relaunch": True,
        # <<< full-edition
        # >>> full-edition
        "allow_conf_edit": False,  # the full restore edits OrcaSlicer.conf: explicit opt-in
        # <<< full-edition
        "language": "auto",
        "sort_on_sync": True,
    }


def norm_color(value):
    value = str(value or "").strip().lstrip("#").upper()
    if len(value) == 8:  # RRGGBBAA
        value = value[:6]
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if not re.fullmatch(r"[0-9A-F]{6}", value):
        return "#FFFFFF"
    return "#" + value


def norm_nozzle(value):
    """'0.40', '0.4mm', ['0.4', '0.4'] -> '0.4'; unknown -> ''."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    match = re.search(r"\d+(?:\.\d+)?", str(value or "").split(",")[0].split(";")[0])
    if not match:
        return ""
    return ("%.2f" % float(match.group(0))).rstrip("0").rstrip(".")


def nozzle_from_name(name):
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*nozzle", name or "", re.I)
    return norm_nozzle(match.group(1)) if match else ""


def slot_presets(slot):
    presets = slot.get("presets")
    if isinstance(presets, dict):
        return {str(k): str(v).strip() for k, v in presets.items() if str(v or "").strip()}
    return {}


def preset_for(slot, nozzle):
    presets = slot_presets(slot)
    return presets.get(norm_nozzle(nozzle) or "-") or presets.get(DEFAULT_VARIANT) or ""


def variants_of(std):
    """Column keys: 'default' plus every nozzle used by the printers or by any slot."""
    keys = {norm_nozzle(n) for n in std.get("printers", {}).values()}
    for slot in std.get("slots", []):
        keys.update(k for k in slot_presets(slot) if k != DEFAULT_VARIANT)
    keys.discard("")
    return [DEFAULT_VARIANT] + sorted(keys, key=float)


def clean_standard(data):
    """Validate and normalise a standard coming from the page, a file or an import."""
    if not isinstance(data, dict):
        raise ValueError("standard must be an object")
    std = empty_standard()
    for key in ("spoolman_url", "spoolman_consent", "language"):
        if isinstance(data.get(key), str):
            std[key] = data[key].strip()
    for key in ("auto_new_project", "relaunch", "sort_on_sync", "allow_conf_edit"):
        if key in data:
            std[key] = bool(data[key])
    if std["language"] not in ("auto",) + LANGUAGES:
        std["language"] = "auto"
    for slot in data.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        presets = slot_presets(slot)
        if not presets.get(DEFAULT_VARIANT):
            if not presets:
                continue
            presets[DEFAULT_VARIANT] = next(iter(presets.values()))
        spool = slot.get("spool")
        spool = int(spool) if str(spool if spool is not None else "").strip().isdigit() else None
        std["slots"].append({"presets": presets, "color": norm_color(slot.get("color")), "spool": spool})
    printers = data.get("printers") or {}
    if isinstance(printers, list):
        printers = {name: nozzle_from_name(name) for name in printers}
    std["printers"] = {str(k): norm_nozzle(v) or nozzle_from_name(k) for k, v in printers.items() if str(k).strip()}
    for key, value in (data.get("spool_map") or {}).items():
        presets = {str(k): str(v).strip() for k, v in (value or {}).items() if str(v or "").strip()}
        if presets.get(DEFAULT_VARIANT):
            std["spool_map"][str(key)] = presets
    for name, price in (data.get("prices") or {}).items():
        try:
            std["prices"][str(name)] = round(float(price), 2)
        except (TypeError, ValueError):
            pass
    return std


def migrate_legacy(old, printer_names=()):
    """Convert the pre-2.0 format (p04/p02 columns, machine_regex) into the current one."""
    data = {
        "slots": [], "spool_map": {}, "prices": old.get("prices") or {},
        "auto_new_project": old.get("auto_new_project", False),
        # >>> full-edition
        "relaunch": old.get("relaunch", True),
        # <<< full-edition
        "language": "pt",
    }

    def presets(entry):
        result = {DEFAULT_VARIANT: entry.get("p04") or ""}
        if entry.get("p02") and entry.get("p02") != entry.get("p04"):
            result["0.2"] = entry["p02"]
        return result

    for slot in old.get("slots") or []:
        data["slots"].append({"presets": presets(slot), "color": slot.get("color"), "spool": slot.get("spool")})
    for key, value in (old.get("spool_map") or {}).items():
        data["spool_map"][key] = presets(value)
    rx = old.get("machine_regex")
    if rx:
        try:
            pattern = re.compile(rx)
            data["printers"] = {name: nozzle_from_name(name) for name in printer_names if pattern.search(name)}
        except re.error:
            pass
    return clean_standard(data)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except Exception:
        return default


def write_json_atomic(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# >>> full-edition
# ---------------------------------------------------------------- flushing volumes
def flush_volume(src, dst):
    """OrcaSlicer's colour-based flushing volume (FlushVolCalc), without the minimum purge."""
    r1, g1, b1 = [int(norm_color(src)[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r2, g2, b2 = [int(norm_color(dst)[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    h1, s1, v1 = colorsys.rgb_to_hsv(r1, g1, b1)
    h2, s2, v2 = colorsys.rgb_to_hsv(r2, g2, b2)
    h1 *= 2 * math.pi
    h2 *= 2 * math.pi
    dx = math.cos(h1) * s1 * v1 - math.cos(h2) * s2 * v2
    dy = math.sin(h1) * s1 * v1 - math.sin(h2) * s2 * v2
    hs = min(1.2, math.hypot(dx, dy))
    l1 = r1 * 0.3 + g1 * 0.59 + b1 * 0.11
    l2 = r2 * 0.3 + g2 * 0.59 + b2 * 0.11
    if l2 >= l1:
        lumi = (l2 - l1) ** 0.7 * 560
    else:
        lumi = (l1 - l2) * 80
        hs = min(0.67 * v2 + 0.33 * v1, hs)
    hsf = 230 * hs
    vol = math.sqrt(hsf * hsf + lumi * lumi - 2 * hsf * lumi * math.cos(math.radians(120)))
    return max(vol, 60)


def flush_matrix(colors, extruders=1):
    one = [
        "0.000000" if i == j else "%.6f" % min(int(flush_volume(a, b)) + FLUSH_OFFSET, FLUSH_MAX)
        for i, a in enumerate(colors) for j, b in enumerate(colors)
    ]
    return "|".join(one * max(1, extruders))


# ---------------------------------------------------------------- OrcaSlicer.conf
def read_conf(path):
    raw = open(path, "rb").read()
    cut = raw.rfind(b"# MD5 checksum")
    if cut < 0:
        raise RuntimeError("OrcaSlicer.conf has no checksum line; unknown format")
    return json.loads(raw[:cut])


def conf_checksum(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest().upper()


def dump_conf(conf):
    """Serialise exactly like OrcaSlicer (tab indent, LF in the checksum, CRLF on Windows disk)."""
    text = json.dumps(conf, indent="\t", ensure_ascii=False)
    return text, conf_checksum(text)


def write_conf(path, conf):
    text, md5 = dump_conf(conf)
    tmp = path + ".filament-standard.tmp"
    newline = "\r\n" if os.name == "nt" else "\n"
    with open(tmp, "w", encoding="utf-8", newline=newline) as stream:
        stream.write(text + "\n# MD5 checksum " + md5 + "\n")
    os.replace(tmp, path)


def verify_conf(path):
    raw = open(path, "rb").read()
    cut = raw.rfind(b"# MD5 checksum")
    body = raw[:cut].replace(b"\r\n", b"\n").rstrip(b"\n")
    expected = raw[cut:].split()[-1].decode()
    return hashlib.md5(body).hexdigest().upper() == expected.upper()


_SLOT_KEY = re.compile(r"filament_\d\d")


def entry_filaments(entry):
    keys = sorted(k for k in entry if _SLOT_KEY.fullmatch(k))
    return ([entry["filament"]] if "filament" in entry else []) + [entry[k] for k in keys]


def apply_lists(conf, std):
    """Write the standard into every orca_presets entry of the selected printers.

    Returns (changed printer names, selected printers without an entry yet).
    """
    slots = std["slots"]
    if not slots:
        raise RuntimeError("the standard list is empty")
    colors = [norm_color(s.get("color")) for s in slots]
    n = len(colors)
    fills = {"filament_is_mixed": "0", "filament_mixed_gradient": "0", "filament_mixed_gradient_per_part": "0"}
    seps = {"filament_mixed_components": "|", "filament_mixed_gradient_curve": ";",
            "filament_mixed_gradient_range": "|", "filament_mixed_sublayer_ratios": "|"}
    handled = {"filament", "filament_colors", "filament_multi_colors", "filament_color_types"} | set(fills) | set(seps)
    printers = std.get("printers") or {}
    changed = []
    for entry in conf.get("orca_presets", []):
        machine = entry.get("machine", "")
        if machine not in printers:
            continue
        nozzle = printers[machine] or nozzle_from_name(machine)
        old_n = max(1, len(entry_filaments(entry)))
        names = [preset_for(s, nozzle) for s in slots]
        for key in [k for k in entry if _SLOT_KEY.fullmatch(k)]:
            del entry[key]
        entry["filament"] = names[0]
        for i, name in enumerate(names[1:], 1):
            entry["filament_%02d" % i] = name
        entry["filament_colors"] = entry["filament_multi_colors"] = ",".join(colors)
        entry["filament_color_types"] = ",".join(["1"] * n)
        old_matrix = [v for v in str(entry.get("flush_volumes_matrix", "")).split("|") if v]
        extruders = len(old_matrix) // (old_n * old_n) if old_matrix and len(old_matrix) % (old_n * old_n) == 0 else 1
        entry["flush_multiplier"] = entry.get("flush_multiplier") or "1.000000"
        entry["flush_volumes_matrix"] = flush_matrix(colors, extruders)
        old_vector = [v for v in str(entry.get("flush_volumes_vector", "")).split("|") if v]
        per = len(old_vector) // old_n if old_vector and len(old_vector) % old_n == 0 else 2
        entry["flush_volumes_vector"] = "|".join([(old_vector or ["140.000000"])[0]] * (max(1, per) * n))
        for key in list(entry):
            if key in fills:
                entry[key] = ",".join([fills[key]] * n)
            elif key in seps:
                entry[key] = seps[key] * (n - 1)
            elif key.startswith("filament_") and key not in handled and not _SLOT_KEY.fullmatch(key):
                values = str(entry[key]).split(",")
                if len(values) == old_n and old_n > 1:  # unknown per-slot list: resize, keep the first value
                    entry[key] = ",".join((values + [values[0]] * n)[:n])
        changed.append(machine)
    missing = sorted(set(printers) - set(changed))
    return changed, missing


def apply_prices(filament_dir, prices, user_id=""):
    """Write filament_cost into the user presets whose price changed. Returns [(name, old, new)]."""
    done = []
    now = str(int(time.time()))
    for name, price in sorted(prices.items()):
        path = os.path.join(filament_dir, name + ".json")
        if not os.path.isfile(path):
            continue
        data = read_json(path)
        if not isinstance(data, dict):
            continue
        new = "%.2f" % float(price)
        old = (data.get("filament_cost") or [""])[0]
        try:
            if old and abs(float(old) - float(new)) < 0.005:
                continue
        except ValueError:
            pass
        data["filament_cost"] = [new]
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(data, indent="\t", ensure_ascii=False, sort_keys=True) + "\n")
        info_path = os.path.join(filament_dir, name + ".info")
        info = {}
        if os.path.isfile(info_path):
            for line in open(info_path, encoding="utf-8"):
                if " = " in line:
                    k, v = line.rstrip("\n").split(" = ", 1)
                    info[k] = v
        with open(info_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("sync_info = %s\nuser_id = %s\nsetting_id = %s\nbase_id = %s\nupdated_time = %s\n" % (
                "update" if info.get("setting_id") else "create", info.get("user_id") or user_id,
                info.get("setting_id", ""), info.get("base_id", ""), now))
        done.append((name, old, new))
    return done


BACKUP_FILE = "orca_presets.json"


def restore(data_dir, std, log=print):
    """Apply the standard to an OrcaSlicer data folder. OrcaSlicer must be closed.

    OrcaSlicer.conf also holds other settings, including printer access codes. Only the
    ``orca_presets`` entries of the selected printers are changed; every other key is written
    back unchanged and is never logged or copied. The backup holds just the entries that change.
    """
    conf_path = os.path.join(data_dir, "OrcaSlicer.conf")
    conf = read_conf(conf_path)
    printers = set(std.get("printers") or {})
    before = [json.loads(json.dumps(e)) for e in conf.get("orca_presets", []) if e.get("machine") in printers]
    backup = os.path.join(data_dir, "backup-filament-standard-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    write_json_atomic(os.path.join(backup, BACKUP_FILE), {"orca_presets": before})
    changed, missing = apply_lists(conf, std)
    write_conf(conf_path, conf)
    log("list with %d slots written to %d printer profile(s): %s" % (len(std["slots"]), len(changed), ", ".join(changed)))
    if missing:
        log("skipped (never selected in OrcaSlicer, no saved list yet): %s" % ", ".join(missing))
    user_id = (conf.get("app") or {}).get("preset_folder") or ""
    if std.get("prices"):
        fdir = os.path.join(data_dir, "user", user_id or "default", "filament")
        if os.path.isdir(fdir):
            names = [n for n in std["prices"] if os.path.isfile(os.path.join(fdir, n + ".json"))]
            if names:
                os.makedirs(os.path.join(backup, "filament"), exist_ok=True)
            for name in names:
                for ext in (".json", ".info"):
                    src = os.path.join(fdir, name + ext)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join(backup, "filament", name + ext))
            changes = apply_prices(fdir, std["prices"], user_id)
            for name, old, new in changes:
                log("price %s: %s -> %s" % (name, old or "-", new))
            if not changes:
                log("prices: no preset needed a change")
    log("backup in %s" % backup)
    return changed, missing, backup


def undo(data_dir, backup, log=print):
    """Put back the orca_presets entries and filament presets saved by restore(). OrcaSlicer must be closed."""
    saved = read_json(os.path.join(backup, BACKUP_FILE))
    if not isinstance(saved, dict):
        raise RuntimeError("not a FilamentStandard backup: %s" % backup)
    conf_path = os.path.join(data_dir, "OrcaSlicer.conf")
    conf = read_conf(conf_path)
    entries = {e.get("machine"): e for e in saved.get("orca_presets", [])}
    presets = conf.get("orca_presets", [])
    for i, entry in enumerate(presets):
        if entry.get("machine") in entries:
            presets[i] = entries[entry["machine"]]
    write_conf(conf_path, conf)
    log("restored %d printer profile(s): %s" % (len(entries), ", ".join(entries)))
    fbackup = os.path.join(backup, "filament")
    if os.path.isdir(fbackup):
        user_id = (conf.get("app") or {}).get("preset_folder") or "default"
        fdir = os.path.join(data_dir, "user", user_id, "filament")
        for name in os.listdir(fbackup):
            shutil.copy2(os.path.join(fbackup, name), os.path.join(fdir, name))
        log("restored the filament presets from %s" % fbackup)
    return list(entries)


# ---------------------------------------------------------------- helper process
def _no_window():
    return 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW


def orca_running():
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq orca-slicer.exe", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, creationflags=_no_window()).stdout
            return "orca-slicer.exe" in out.lower()
        for name in ("orca-slicer", "OrcaSlicer"):
            if subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0:
                return True
        return False
    except Exception:
        return False


def find_python():
    names = ("pythonw", "pyw", "python", "py") if os.name == "nt" else ("python3", "python")
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return ""


def run_job(job_path, wait=True, poll=2.0):
    """Runs outside OrcaSlicer: wait for it to close, apply the standard, reopen it if asked."""
    job = read_json(job_path)
    if not job:
        raise RuntimeError("invalid job: %s" % job_path)
    folder = os.path.dirname(job_path)
    log_path = os.path.join(folder, LOG_FILE)

    def log(msg):
        with open(log_path, "a", encoding="utf-8") as stream:
            stream.write("%s %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))

    exe = job.get("orca_exe") or ""
    log("waiting for OrcaSlicer to close")
    deadline = time.time() + 6 * 3600
    while wait and orca_running():
        if not os.path.exists(job_path):
            log("cancelled by the plugin")
            return 1
        if time.time() > deadline:
            log("gave up: OrcaSlicer stayed open for 6 h")
            return 2
        time.sleep(poll)
    if wait:
        time.sleep(poll)  # OrcaSlicer writes its configuration while exiting
    if not os.path.exists(job_path):
        log("cancelled by the plugin")
        return 1
    # the latest standard saved by the plugin wins over the snapshot taken when scheduling
    std = read_json(os.path.join(folder, STD_FILE))
    std = clean_standard(std) if isinstance(std, dict) and std.get("slots") else clean_standard(job["standard"])
    try:
        restore(job["data_dir"], std, log)
    except Exception as exc:
        log("ERROR: %s" % exc)
        return 3
    finally:
        try:
            os.remove(job_path)
        except OSError:
            pass
    if job.get("relaunch") and exe:
        try:
            subprocess.Popen([exe], close_fds=True, start_new_session=(os.name != "nt"))
            log("OrcaSlicer reopened")
        except Exception as exc:
            log("could not reopen OrcaSlicer: %s" % exc)
    return 0


# <<< full-edition


# ---------------------------------------------------------------- Spoolman
def spoolman_origin(url):
    parts = urllib.parse.urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    return "%s://%s" % (parts.scheme, parts.netloc)


def fetch_spools(base_url, timeout=10):
    if not spoolman_origin(base_url):
        raise ValueError("invalid Spoolman URL: %r" % base_url)
    url = base_url.rstrip("/") + "/api/v1/spool?allow_archived=false"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def spool_key(spool):
    fil = spool.get("filament") or {}
    vendor = (fil.get("vendor") or {}).get("name") or "?"
    return "%s|%s" % (vendor, fil.get("name") or fil.get("material") or "?")


def spool_info(spool):
    fil = spool.get("filament") or {}
    weight = spool.get("initial_weight") or fil.get("weight") or 1000
    price = spool.get("price") if spool.get("price") is not None else fil.get("price")
    multi = (fil.get("multi_color_hexes") or "").split(",")[0]
    try:
        price_kg = float(price) * 1000.0 / float(weight) if price is not None and weight else None
    except (TypeError, ValueError, ZeroDivisionError):
        price_kg = None
    return {
        "id": spool.get("id"),
        "key": spool_key(spool),
        "material": (fil.get("material") or "").upper(),
        "color": norm_color(fil.get("color_hex") or multi),
        "price_kg": price_kg,
    }


MATERIAL_ORDER = {"PLA": 0, "PETG": 1}


def guess_material(name):
    up = (name or "").upper()
    for mat in ("PETG", "ABS", "ASA", "TPU", "PCTG", "PC", "PA", "PVA", "HIPS", "PLA"):
        if re.search(r"(^|[^A-Z])%s([^A-Z]|$)" % mat, up) or (mat == "PLA" and "PLA" in up):
            return mat
    return ""


def sort_slots(slots, materials, vendors=None):
    """PLA white, PLA black, other PLA; PETG white, PETG black, other PETG; then other materials.

    Inside a material the current order is kept per brand; new slots end their brand group.
    The brand comes from ``vendors`` (Spoolman) or, failing that, the first word of the preset name.
    """
    vendors = vendors or {}
    order = {id(s): i for i, s in enumerate(slots)}

    def vendor_of(slot):
        return (vendors.get(id(slot)) or (preset_for(slot, "").split() or [""])[0]).lower()

    first = {}
    for slot in slots:
        first.setdefault((materials.get(id(slot), ""), vendor_of(slot)), order[id(slot)])

    def rank(slot):
        mat = materials.get(id(slot), "")
        color = norm_color(slot.get("color"))
        tone = 0 if color == "#FFFFFF" else 1 if color == "#000000" else 2
        group = first[(mat, vendor_of(slot))] if tone == 2 else 0
        return (MATERIAL_ORDER.get(mat, 9), mat, tone, group, order[id(slot)])

    return sorted(slots, key=rank)


def plan_sync(std, spools):
    """Compare the standard with the active spools. std is not modified; returns a proposal."""
    infos = [spool_info(s) for s in spools]
    by_id = {i["id"]: i for i in infos}
    spool_map = std.get("spool_map", {})
    known = {s.get("spool") for s in std["slots"] if s.get("spool")}
    keep, removed, recolored = [], [], []
    for slot in std["slots"]:
        sid = slot.get("spool")
        if sid and sid not in by_id:
            removed.append(slot)
            continue
        new = json.loads(json.dumps(slot))
        if sid and norm_color(slot.get("color")) != by_id[sid]["color"]:
            recolored.append({"spool": sid, "from": norm_color(slot.get("color")), "to": by_id[sid]["color"]})
            new["color"] = by_id[sid]["color"]
        keep.append(new)
    added, unmapped = [], []
    for info in infos:
        if info["id"] in known:
            continue
        mapped = spool_map.get(info["key"])
        if not mapped:
            unmapped.append(info)
            continue
        if any(preset_for(s, "") == mapped[DEFAULT_VARIANT] and norm_color(s.get("color")) == info["color"] for s in keep):
            continue  # a second spool of the same filament and colour is not a new slot
        slot = {"presets": dict(mapped), "color": info["color"], "spool": info["id"]}
        keep.append(slot)
        added.append(slot)
    if std.get("sort_on_sync", True):
        mats, vendors = {}, {}
        for slot in keep:
            sid = slot.get("spool")
            mats[id(slot)] = by_id[sid]["material"] if sid in by_id else guess_material(preset_for(slot, ""))
            if sid in by_id:
                vendors[id(slot)] = by_id[sid]["key"].split("|")[0]
        keep = sort_slots(keep, mats, vendors)
    sums = {}
    for info in infos:
        mapped = spool_map.get(info["key"])
        if mapped and info["price_kg"]:
            for name in set(mapped.values()):
                sums.setdefault(name, []).append(info["price_kg"])
    prices = dict(std.get("prices", {}))
    price_changes = []
    for name, values in sorted(sums.items()):
        avg = round(sum(values) / len(values), 2)
        if abs(prices.get(name, -1) - avg) >= 0.005:
            price_changes.append({"preset": name, "from": prices.get(name), "to": avg})
        prices[name] = avg
    return {"slots": keep, "prices": prices, "added": added, "removed": removed,
            "recolored": recolored, "unmapped": unmapped, "price_changes": price_changes}


# ---------------------------------------------------------------- inside OrcaSlicer
# >>> full-edition
def data_dir_from(path):
    """OrcaSlicer data folder from the plugin's own location (.../<data_dir>/orca_plugins/...)."""
    path = os.path.abspath(path)
    while True:
        parent, name = os.path.split(path)
        if name == "orca_plugins":
            return parent
        if not parent or parent == path:
            return ""
        path = parent


# <<< full-edition


def storage_from(path):
    """plugin_data folder of this installation, derived like PluginManager::get_storage_dir.

    local:      orca_plugins/<key>[.py|.whl]/...          -> orca_plugins/plugin_data/<key>
    subscribed: orca_plugins/_subscribed/<user>/<key>/... -> orca_plugins/plugin_data/_subscribed/<user>/<key>
    """
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    if "orca_plugins" not in parts:
        return ""
    i = len(parts) - 1 - parts[::-1].index("orca_plugins")
    root = os.sep.join(parts[:i + 1])
    rest = parts[i + 1:]
    if len(rest) >= 3 and rest[0] == "_subscribed":
        return os.path.join(root, "plugin_data", "_subscribed", rest[1], rest[2])
    if rest:
        key = re.sub(r"\.(py|whl)$", "", rest[0])
        return os.path.join(root, "plugin_data", key)
    return ""


# >>> full-edition
OWN_DIR = re.compile(r"filament[_-]?standard", re.I)


def find_previous(storage_dir):
    """Standard left by another installation of this plugin, for a first run.

    Only this plugin's own folders are read, never other plugins' data:
    ``plugin_data/filamentos_padrao`` (1.x) and ``plugin_data/filament_standard*`` (local installs,
    e.g. before subscribing on Orca Cloud). The Spoolman URL and the full-restore opt-in are not
    carried over. Returns ("legacy" | "current", data) or ("", None).
    """
    here = os.path.normcase(os.path.abspath(storage_dir))
    parts = here.split(os.sep)
    if "plugin_data" in parts:
        root = os.sep.join(parts[:len(parts) - parts[::-1].index("plugin_data")])
    else:
        root = os.path.dirname(here)
    try:
        names = os.listdir(root)
    except OSError:
        names = []
    found = []
    for name in names:
        folder = os.path.join(root, name)
        if os.path.normcase(os.path.abspath(folder)) == here:
            continue
        if name in LEGACY_DIRS and os.path.isfile(os.path.join(folder, "padrao.json")):
            found.append(("legacy", os.path.join(folder, "padrao.json")))
        elif OWN_DIR.match(name) and os.path.isfile(os.path.join(folder, STD_FILE)):
            found.append(("current", os.path.join(folder, STD_FILE)))
    found.sort(key=lambda item: (item[0] == "current", os.path.getmtime(item[1])), reverse=True)
    for kind, path in found:
        data = read_json(path)
        if isinstance(data, dict) and data.get("slots"):
            return kind, dict(data, spoolman_url="", spoolman_consent="", allow_conf_edit=False)
    return "", None


# <<< full-edition


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [v for v in re.split(r"[;,]", str(value)) if v]


if orca is not None:

    class FilamentStandardPage(orca.pages.PagesPluginCapabilityBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lock = threading.Lock()
            self.std = None
            self.proposal = None
            self.status = ""
            self.error = ""
            self.busy = False
            self.worker = None
            self.pending_job = False
            self.app_lang = "en"

        # ---- basics
        def get_name(self):
            return "FilamentStandard"

        def get_ui(self):
            return PAGE

        def get_icon(self):
            """OrcaSlicer wants a file: write the embedded SVG next to the plugin data when missing or outdated."""
            try:
                path = self._storage(ICON_FILE)
                current = None
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as stream:
                        current = stream.read()
                if current != TAB_ICON_SVG:
                    with open(path, "w", encoding="utf-8") as stream:
                        stream.write(TAB_ICON_SVG)
                return path
            except Exception:
                traceback.print_exc()
                return ""

        def _storage(self, name):
            folder = str(orca.host.plugin.storage())
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, name)

        def _lang(self):
            choice = (self.std or {}).get("language", "auto")
            return choice if choice in LANGUAGES else self.app_lang

        def _t(self, key, **kwargs):
            return tr(self._lang(), key, **kwargs)

        def _detect_language(self):
            if threading.current_thread() is not threading.main_thread():
                return
            try:
                info = orca.host.app_info()
                self.app_lang = language_for(info.get("language", "") if isinstance(info, dict) else "")
            except Exception:
                try:
                    self.app_lang = language_for(orca.host.app_language())
                except Exception:
                    pass

        def _printer_names(self):
            try:
                return list(orca.host.preset_bundle().printers.preset_names())
            except Exception:
                return []

        def _load(self):
            if self.std is not None:
                return self.std
            data = read_json(self._storage(STD_FILE))
            if isinstance(data, dict):
                self.std = clean_standard(data)
            else:
                self.std = empty_standard()
                # >>> full-edition
                kind, previous = find_previous(str(orca.host.plugin.storage()))
                if previous:
                    self.std = (migrate_legacy(previous, self._printer_names()) if kind == "legacy"
                                else clean_standard(previous))
                    self._save()
                    self.status = self._t("migrated", n=len(self.std["slots"]))
                # <<< full-edition
            self.pending_job = os.path.exists(self._storage(JOB_FILE))
            return self.std


        def _save(self):
            write_json_atomic(self._storage(STD_FILE), self.std)

        def _current(self):
            """(printer name, nozzle, [presets], [colours]) of the current project. UI thread only."""
            bundle = orca.host.preset_bundle()
            printer = bundle.current_printer_preset()
            machine = getattr(printer, "name", "") if printer else ""
            try:
                nozzle = norm_nozzle(bundle.full_config_value("nozzle_diameter"))
            except Exception:
                nozzle = ""
            nozzle = nozzle or nozzle_from_name(machine)
            names = list(bundle.current_filament_preset_names())
            colors = [norm_color(c) for c in as_list(bundle.full_config_value("filament_colour"))]
            return machine, nozzle, names, colors

        def _printer_nozzle(self, name):
            try:
                preset = orca.host.preset_bundle().printers.find_preset(name)
                if preset is not None:
                    nozzle = norm_nozzle(preset.config_value("nozzle_diameter"))
                    if nozzle:
                        return nozzle
            except Exception:
                pass
            return nozzle_from_name(name)

        def _filament_names(self):
            try:
                return sorted(set(orca.host.preset_bundle().filaments.preset_names()), key=str.lower)
            except Exception:
                return []

        def _push(self):
            std = self._load()
            try:
                machine, nozzle, names, colors = self._current()
            except Exception:
                machine, nozzle, names, colors = "", "", [], []
            lang = self._lang()
            self.post_message({
                "type": "state", "std": std, "variants": variants_of(std), "proposal": self.proposal,
                "status": self.status, "error": self.error, "busy": self.busy, "pending_job": self.pending_job,
                "current": {"machine": machine, "nozzle": nozzle, "names": names, "colors": colors},
                "presets": self._filament_names(), "printers": self._printer_names(),
                "version": VERSION, "lang": lang, "i18n": STRINGS[lang],
            })

        # ---- messages from the page (UI thread)
        def on_message(self, data):
            with self.lock:
                cmd = (data or {}).get("cmd")
                self.error = ""
                if cmd not in ("ready", None):
                    self.status = ""
                try:
                    self._detect_language()
                    self._load()
                    handler = {
                        "ready": lambda d: None,
                        "save_std": self._save_std,
                        "capture": lambda d: self._capture(),
                        "restore_live": lambda d: self._restore_live(),
                        # >>> full-edition
                        "restore_full": self._restore_full,
                        "cancel_full": lambda d: self._cancel_full(),
                        # <<< full-edition
                        "sync_preview": self._sync_preview,
                        "apply_prices": lambda d: self._apply_prices(),
                        "sync_apply": self._sync_apply,
                        "sync_discard": lambda d: setattr(self, "proposal", None),
                        "add_current_printer": lambda d: self._add_current_printer(),
                        "import_json": self._import_json,
                        "reset": lambda d: self._reset(),
                    }.get(cmd)
                    if handler is None:
                        raise RuntimeError(self._t("err_unknown", cmd=cmd))
                    handler(data)
                except Exception as exc:
                    traceback.print_exc()
                    self.error = str(exc)
                self._push()

        def _save_std(self, data):
            std = clean_standard(dict(data.get("std") or {}, spool_map=self.std["spool_map"], prices=self.std["prices"]))
            if not std["slots"]:
                raise RuntimeError(self._t("err_empty"))
            for name in std["printers"]:
                if not std["printers"][name]:
                    std["printers"][name] = self._printer_nozzle(name)
            self.std = std
            self._save()
            self.status = self._t("msg_saved", n=len(std["slots"]))

        def _import_json(self, data):
            try:
                parsed = json.loads(data.get("text") or "")
            except ValueError as exc:
                raise RuntimeError(self._t("err_bad_json", error=exc)) from None
            if not isinstance(parsed, dict):
                raise RuntimeError(self._t("err_bad_json", error="expected an object"))
            std = migrate_legacy(parsed, self._printer_names()) if "machine_regex" in parsed or any(
                "p04" in s for s in parsed.get("slots", [])) else clean_standard(parsed)
            self.std = std
            self._save()
            self.status = self._t("msg_imported", n=len(std["slots"]))

        def _reset(self):
            self.std = empty_standard()
            self.proposal = None
            self._save()
            self.status = self._t("msg_reset")

        def _add_current_printer(self):
            machine, nozzle, _, _ = self._current()
            if machine:
                self.std["printers"][machine] = nozzle or self._printer_nozzle(machine)
                self._save()

        def _capture(self):
            machine, nozzle, names, colors = self._current()
            if not names:
                raise RuntimeError(self._t("err_no_current"))
            used = any(nozzle in slot_presets(s) for s in self.std["slots"])
            column = nozzle if (nozzle and used) else DEFAULT_VARIANT
            pool = list(self.std["slots"])
            slots = []
            for i, name in enumerate(names):
                color = colors[i] if i < len(colors) else "#FFFFFF"
                old = next((s for s in pool if slot_presets(s).get(column) == name
                            and norm_color(s.get("color")) == color), None) \
                    or next((s for s in pool if slot_presets(s).get(column) == name), None)
                if old:
                    pool.remove(old)
                presets = dict(slot_presets(old)) if old else {}
                presets[column] = name
                presets.setdefault(DEFAULT_VARIANT, name)
                slots.append({"presets": presets, "color": color, "spool": (old or {}).get("spool")})
            self.std["slots"] = slots
            if machine:
                self.std["printers"].setdefault(machine, nozzle)
            self._save()
            self.status = self._t("msg_captured", n=len(slots), machine=machine or "?", column=column)

        # ---- live restore (presets per slot)
        def _restore_live(self, quiet=False):
            machine, nozzle, names, _ = self._current()
            desired = [preset_for(s, nozzle) for s in self.std["slots"]]
            todo = [(i + 1, desired[i]) for i in range(min(len(names), len(desired)))
                    if desired[i] and names[i] != desired[i]]
            n_cur, n_std = len(names), len(desired)
            if not todo:
                self.status = self._t("msg_live_none", n=min(n_cur, n_std))
            else:
                self._start_worker(todo, n_cur, n_std)
            if n_cur != n_std and not quiet:
                self.status += " " + self._t("msg_count_differs", cur=n_cur, std=n_std)

        def _start_worker(self, todo, n_cur, n_std):
            if self.busy:
                raise RuntimeError(self._t("err_busy"))
            self.busy = True
            self.status = self._t("msg_live_running", n=len(todo))

            def work():
                ok, fails = 0, []
                editor = orca.host.preset.filament
                for slot, name in todo:
                    try:
                        editor.begin_update(slot, name).commit()
                        ok += 1
                    except Exception as exc:
                        fails.append("slot %d (%s): %s" % (slot, name, exc))
                with self.lock:
                    self.busy = False
                    self.status = self._t("msg_live_done", n=ok)
                    if n_cur != n_std:
                        self.status += " " + self._t("msg_count_differs", cur=n_cur, std=n_std)
                    self.error = "; ".join(fails)
                    self.post_message({"type": "refresh_request"})

            self.worker = threading.Thread(target=work, name="filament-standard", daemon=True)
            self.worker.start()

        # >>> full-edition
        # ---- full restore on close
        def _restore_full(self, data):
            if not self.std["slots"]:
                raise RuntimeError(self._t("err_empty"))
            if not self.std.get("allow_conf_edit"):
                raise RuntimeError(self._t("err_conf_edit_off"))
            if not self.std["printers"]:
                raise RuntimeError(self._t("err_no_printers"))
            if data and "relaunch" in data:
                self.std["relaunch"] = bool(data["relaunch"])
                self._save()
            python = find_python()
            if not python:
                raise RuntimeError(self._t("err_no_python"))
            exe = os.environ.get("APPIMAGE") or (
                sys.executable if "orca" in os.path.basename(sys.executable).lower() else "")
            job_path = self._storage(JOB_FILE)
            write_json_atomic(job_path, {
                "data_dir": data_dir_from(os.path.abspath(__file__)) or data_dir_from(job_path),
                "standard": self.std, "relaunch": self.std.get("relaunch", True), "orca_exe": exe,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            args = [python, os.path.abspath(__file__), "--apply", job_path]
            if os.name == "nt":
                subprocess.Popen(args, close_fds=True, creationflags=0x00000008 | 0x00000200)
            else:
                subprocess.Popen(args, close_fds=True, start_new_session=True)
            self.pending_job = True
            after = self._t("msg_after_reopen" if self.std.get("relaunch", True) else "msg_after_closed")
            self.status = self._t("msg_full_scheduled", n=len(self.std["printers"]), after=after)

        def _cancel_full(self):
            try:
                os.remove(self._storage(JOB_FILE))
            except OSError:
                pass
            self.pending_job = False
            self.status = self._t("msg_full_cancelled")

        # <<< full-edition

        # ---- Spoolman
        def _spoolman_allowed(self, consent=False):
            """The plugin connects only to the Spoolman origin the user confirmed."""
            origin = spoolman_origin(self.std.get("spoolman_url"))
            if not origin:
                raise RuntimeError(self._t("err_no_spoolman"))
            if consent and self.std.get("spoolman_consent") != origin:
                self.std["spoolman_consent"] = origin
                self._save()
                try:
                    orca.request_permissions(network=[origin])
                except Exception:
                    pass  # older hosts: OrcaSlicer's own audit prompt still asks
            if self.std.get("spoolman_consent") != origin:
                raise RuntimeError(self._t("err_spoolman_consent"))

        def _sync_preview(self, data=None):
            self._spoolman_allowed(bool((data or {}).get("consent")))
            spools = fetch_spools(self.std["spoolman_url"])
            self.proposal = plan_sync(self.std, spools)
            p = self.proposal
            self.status = self._t("msg_sync", spools=len(spools), added=len(p["added"]), removed=len(p["removed"]),
                                  recolored=len(p["recolored"]), prices=len(p["price_changes"]),
                                  unmapped=len(p["unmapped"]))

        def _sync_apply(self, data):
            if not self.proposal:
                raise RuntimeError(self._t("err_preview_first"))
            mapped = False
            for key, presets in (data.get("map") or {}).items():
                presets = {k: str(v).strip() for k, v in (presets or {}).items() if str(v or "").strip()}
                if presets.get(DEFAULT_VARIANT):
                    self.std["spool_map"][key] = presets
                    mapped = True
            if mapped:  # new mappings: redo the preview with them
                self._spoolman_allowed()
                self.proposal = plan_sync(self.std, fetch_spools(self.std["spoolman_url"]))
            self.std["slots"] = self.proposal["slots"]
            self.std["prices"] = self.proposal["prices"]
            self._save()
            self.proposal = None
            self.status = self._t("msg_sync_applied", n=len(self.std["slots"]))

        # ---- prices (through the API, as unsaved edits)
        def _apply_prices(self):
            if self.busy:
                raise RuntimeError(self._t("err_busy"))
            _, _, names, _ = self._current()
            prices = self.std.get("prices") or {}
            todo, seen = [], set()
            for i, name in enumerate(names):
                if name in prices and name not in seen:
                    seen.add(name)
                    todo.append((i + 1, name, "%.2f" % float(prices[name])))
            if not todo:
                self.status = self._t("msg_prices_none")
                return
            self.busy = True
            self.status = self._t("msg_prices_running", n=len(todo))

            def work():
                ok, fails = 0, []
                editor = orca.host.preset.filament
                for slot, name, price in todo:
                    try:
                        transaction = editor.begin_update(slot)
                        transaction.set("filament_cost", price)
                        transaction.commit()
                        ok += 1
                    except Exception as exc:
                        fails.append("%s: %s" % (name, exc))
                with self.lock:
                    self.busy = False
                    self.status = self._t("msg_prices_done", n=ok)
                    self.error = "; ".join(fails)
                    self.post_message({"type": "refresh_request"})

            self.worker = threading.Thread(target=work, name="filament-standard-prices", daemon=True)
            self.worker.start()

        # ---- events
        def on_lifecycle_event(self, event, ctx):
            try:
                if event != getattr(orca.LifecycleEvent, "NewProject", None):
                    return
                if not self._load().get("auto_new_project"):
                    return
                if threading.current_thread() is threading.main_thread():
                    with self.lock:
                        self._restore_live(quiet=True)
                        self._push()
                else:
                    self.post_message({"type": "auto_request"})
            except Exception:
                traceback.print_exc()

    def declare_permissions():
        """Ask for threads and, when configured, the Spoolman host while the plugin loads."""
        network = []
        storage = storage_from(os.path.abspath(__file__))
        if storage:
            saved = read_json(os.path.join(storage, STD_FILE)) or {}
            origin = spoolman_origin(saved.get("spoolman_url"))
            if origin and saved.get("spoolman_consent") == origin:  # only a host the user confirmed
                network.append(origin)
        try:
            orca.request_permissions(threading=True, network=network)
        except TypeError:
            try:
                orca.request_permissions(threading=True)
            except Exception:
                traceback.print_exc()

    @orca.plugin
    class FilamentStandardPlugin(orca.base):
        def register_capabilities(self):
            declare_permissions()
            orca.register_capability(FilamentStandardPage)


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#f6f7f8;--card:#fff;--fg:#1d2125;--mute:#69737d;--line:#dde1e5;--acc:#009688;--warn:#b26a00;--err:#c62828}
@media (prefers-color-scheme:dark){:root{--bg:#1f2124;--card:#2a2d31;--fg:#e8eaed;--mute:#9aa3ab;--line:#3a3e44;--acc:#26a69a;--warn:#f0a030;--err:#ef5350}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:14px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:12px 0}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:7px 12px;font:inherit;cursor:pointer}
button.sec{background:transparent;color:var(--fg);border:1px solid var(--line)}
button.mini{padding:2px 7px}
button:disabled{opacity:.5;cursor:default}
.mute{color:var(--mute)}.err{color:var(--err)}.warn{color:var(--warn)}.ok{color:var(--acc)}.diff{color:var(--warn)}
table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:middle}
th{font-weight:600;color:var(--mute);font-size:12px}
input[type=text],select,textarea{background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:3px 5px;font:inherit}
td input[type=text]{width:100%}td input.num{width:56px}
input[type=color]{width:34px;height:24px;border:1px solid var(--line);padding:0;background:none}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid var(--line);vertical-align:middle}
label{display:inline-flex;gap:6px;align-items:center}.small{font-size:12px}
.scroll{max-height:220px;overflow:auto;border:1px solid var(--line);border-radius:6px;padding:6px}
textarea{width:100%;min-height:140px;font-family:Consolas,monospace;font-size:12px}
</style></head><body><main>
<h1 data-i18n="title"></h1>
<div class="mute" id="cur"></div>
<div id="msg" class="card" style="display:none"></div>

<div class="card"><h2 data-i18n="actions"></h2>
<div class="row">
<button id="b-live" data-i18n="restore_live" data-i18n-title="restore_live_tip"></button>
<!-- >>> full-edition -->
<button id="b-full" data-i18n="restore_full" data-i18n-title="restore_full_tip"></button>
<label class="small"><input type="checkbox" id="relaunch"> <span data-i18n="relaunch"></span></label>
<button class="sec" id="b-cancel" style="display:none" data-i18n="cancel_full"></button>
<!-- <<< full-edition -->
</div>
<div class="row" style="margin-top:8px">
<button class="sec" id="b-capture" data-i18n="capture" data-i18n-title="capture_tip"></button>
<button class="sec" id="b-sync" data-i18n="sync"></button>
<button class="sec" id="b-prices" data-i18n="apply_prices" data-i18n-title="apply_prices_tip"></button>
<label class="small"><input type="checkbox" id="auto"> <span data-i18n="auto"></span></label>
</div></div>

<div class="card" id="sync" style="display:none"></div>

<div class="card"><h2 data-i18n="standard"></h2>
<table><thead id="head"></thead><tbody id="rows"></tbody></table>
<div class="row" style="margin-top:8px">
<button class="sec" id="b-add" data-i18n="add_slot"></button>
<button id="b-save" data-i18n="save"></button>
</div></div>

<div class="card"><h2 data-i18n="printers"></h2>
<div class="mute small" id="printers-help"></div>
<div class="row" style="margin:6px 0"><input type="text" id="pfilter"><button class="sec" id="b-addprinter" data-i18n="add_current_printer"></button></div>
<div class="scroll" id="plist"></div>
</div>

<div class="card"><h2 data-i18n="settings"></h2>
<div class="row"><label><span data-i18n="spoolman_url"></span> <input type="text" id="url" size="40"></label>
<span class="mute small" data-i18n="spoolman_help"></span></div>
<div class="row" style="margin-top:6px"><label><span data-i18n="language"></span>
<select id="lang"><option value="auto" data-i18n="lang_auto"></option><option value="en">English</option><option value="pt">Português</option></select></label></div>
<div class="row" style="margin-top:6px"><label class="small"><input type="checkbox" id="sortsync"> <span data-i18n="sort_on_sync"></span></label></div>
<div class="row" style="margin-top:8px"><button class="sec" id="b-reset" data-i18n="reset"></button><span class="mute small" id="ver"></span></div>
</div>

<!-- >>> full-edition -->
<div class="card"><h2 data-i18n="full_section"></h2>
<label class="small"><input type="checkbox" id="confedit"> <span data-i18n="allow_conf_edit"></span></label>
<div class="mute small" style="margin-top:6px" data-i18n="allow_conf_edit_help"></div>
</div>
<!-- <<< full-edition -->

<div class="card"><h2 data-i18n="json"></h2>
<div class="row"><button class="sec" id="b-export" data-i18n="json_export"></button><button class="sec" id="b-import" data-i18n="json_import"></button></div>
<textarea id="json" style="margin-top:8px;display:none"></textarea>
</div>
<datalist id="presets"></datalist>
</main>
<script>
let S=null, slots=[], printers={}, T={};
const $=id=>document.getElementById(id);
const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const t=(k,a)=>{let s=T[k]||k;if(a)for(const x in a)s=s.split('{'+x+'}').join(a[x]);return s;};
const send=m=>orca.postMessage(m);
const chk=(id,d)=>$(id)?$(id).checked:d;
const origin=u=>{try{const x=new URL(u);return /^https?:$/.test(x.protocol)?x.origin:'';}catch(e){return '';}};
const want=(s,n)=>(s.presets&&(s.presets[n]||s.presets['default']))||'';
function collect(){return Object.assign({},S.std,{slots:slots,printers:printers,spoolman_url:$('url').value,
  auto_new_project:$('auto').checked,relaunch:chk('relaunch',S.std.relaunch!==false),allow_conf_edit:chk('confedit',!!S.std.allow_conf_edit),language:$('lang').value,sort_on_sync:$('sortsync').checked});}
function i18n(){document.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));
  document.querySelectorAll('[data-i18n-title]').forEach(e=>e.title=t(e.dataset.i18nTitle));
  $('pfilter').placeholder=t('filter');document.documentElement.lang=S.lang==='pt'?'pt-BR':'en';}
function variants(){const v=['default'];Object.values(printers).forEach(n=>{if(n&&v.indexOf(n)<0)v.push(n);});
  slots.forEach(s=>Object.keys(s.presets||{}).forEach(k=>{if(v.indexOf(k)<0)v.push(k);}));
  return ['default'].concat(v.slice(1).sort((a,b)=>parseFloat(a)-parseFloat(b)));}
function render(){
  i18n();
  const c=S.current, V=variants();
  $('cur').textContent=t('current',{machine:c.machine||'?',nozzle:c.nozzle||'?',n:c.names.length});
  const m=$('msg');
  if(S.error||S.status){m.style.display='';m.innerHTML=(S.status?'<div>'+esc(S.status)+'</div>':'')+(S.error?'<div class="err">'+esc(S.error)+'</div>':'');}
  else if(!slots.length){m.style.display='';m.innerHTML='<div class="mute">'+esc(t('first_run'))+'</div>';}
  else m.style.display='none';
  $('presets').innerHTML=S.presets.map(p=>'<option value="'+esc(p)+'">').join('');
  $('head').innerHTML='<tr><th>#</th><th>'+esc(t('col_color'))+'</th>'+V.map(v=>'<th>'+esc(v==='default'?t('col_variant_default'):t('col_variant',{nozzle:v}))+'</th>').join('')+
    '<th>'+esc(t('col_spool'))+'</th><th>'+esc(t('col_project'))+'</th><th></th></tr>';
  $('rows').innerHTML=slots.map((s,i)=>{
    const w=want(s,c.nozzle), have=c.names[i], hc=c.colors[i];
    const st=have==null?'<span class="mute">-</span>':
      (have===w&&(hc||'').toUpperCase()===(s.color||'').toUpperCase()?'<span class="ok">'+esc(t('ok'))+'</span>':
      '<span class="diff" title="'+esc(have)+' '+esc(hc||'')+'">'+(hc?'<span class="sw" style="background:'+esc(hc)+'"></span> ':'')+esc(have)+'</span>');
    return '<tr><td>'+(i+1)+'</td><td><input type="color" data-i="'+i+'" data-k="color" value="'+esc(s.color)+'"></td>'+
      V.map(v=>'<td><input type="text" list="presets" data-i="'+i+'" data-v="'+esc(v)+'" value="'+esc((s.presets||{})[v]||'')+'"></td>').join('')+
      '<td><input type="text" class="num" data-i="'+i+'" data-k="spool" value="'+esc(s.spool==null?'':s.spool)+'"></td>'+
      '<td class="small">'+st+'</td><td style="white-space:nowrap">'+
      '<button class="sec mini" data-a="up" data-i="'+i+'">↑</button> <button class="sec mini" data-a="down" data-i="'+i+'">↓</button> '+
      '<button class="sec mini" data-a="del" data-i="'+i+'">✕</button></td></tr>';}).join('');
  $('printers-help').textContent=t('printers_help',{nozzle:c.nozzle||'0.2'});
  renderPrinters();
  $('url').value=S.std.spoolman_url||'';$('lang').value=S.std.language||'auto';
  $('auto').checked=!!S.std.auto_new_project;$('sortsync').checked=S.std.sort_on_sync!==false;
  ['b-live','b-sync','b-capture','b-prices'].forEach(id=>$(id).disabled=!!S.busy);
// >>> full-edition
  $('confedit').checked=!!S.std.allow_conf_edit;$('relaunch').checked=S.std.relaunch!==false;
  $('b-cancel').style.display=S.pending_job?'':'none';
  $('b-full').disabled=!!S.busy||!S.std.allow_conf_edit;
// <<< full-edition
  $('ver').textContent='FilamentStandard v'+S.version;
  renderSync();
}
function renderPrinters(){
  const f=$('pfilter').value.toLowerCase();
  const names=Array.from(new Set(S.printers.concat(Object.keys(printers)))).sort((a,b)=>(printers[b]!==undefined)-(printers[a]!==undefined)||a.localeCompare(b));
  $('plist').innerHTML=names.filter(n=>!f||n.toLowerCase().indexOf(f)>=0).map(n=>{const on=printers[n]!==undefined;
    return '<div class="row small"><label><input type="checkbox" data-p="'+esc(n)+'"'+(on?' checked':'')+'> '+esc(n)+'</label>'+
      (on?'<span class="mute">'+esc(t('nozzle'))+'</span><input type="text" class="num" data-pn="'+esc(n)+'" value="'+esc(printers[n]||'')+'" size="4">':'')+'</div>';}).join('');
}
function renderSync(){
  const p=S.proposal, box=$('sync');
  if(!p){box.style.display='none';return;}
  box.style.display='';
  const li=a=>a.length?'<ul>'+a.join('')+'</ul>':'<div class="mute">'+esc(t('none'))+'</div>';
  const sw=c=>'<span class="sw" style="background:'+esc(c)+'"></span> ';
  let h='<h2>'+esc(t('sync_title'))+'</h2>';
  h+='<b>'+esc(t('sync_added'))+'</b>'+li(p.added.map(s=>'<li>'+sw(s.color)+esc(want(s,''))+' ('+esc(t('spool_n',{id:s.spool}))+')</li>'));
  h+='<b>'+esc(t('sync_removed'))+'</b>'+li(p.removed.map(s=>'<li>'+sw(s.color)+esc(want(s,''))+' ('+esc(t('spool_n',{id:s.spool}))+')</li>'));
  h+='<b>'+esc(t('sync_recolored'))+'</b>'+li(p.recolored.map(r=>'<li>'+esc(t('spool_n',{id:r.spool}))+': '+sw(r.from)+esc(r.from)+' → '+sw(r.to)+esc(r.to)+'</li>'));
  h+='<b>'+esc(t('sync_prices'))+'</b>'+li(p.price_changes.map(r=>'<li>'+esc(r.preset)+': '+(r.from==null?'-':r.from)+' → '+r.to+'</li>'));
  if(p.unmapped.length){
    const V=variants();
    h+='<b class="warn">'+esc(t('sync_unmapped'))+'</b><div class="mute small">'+esc(t('sync_unmapped_help'))+'</div><table>';
    const seen={};
    p.unmapped.forEach(u=>{if(seen[u.key])return;seen[u.key]=1;
      h+='<tr><td>'+sw(u.color)+esc(u.key)+' ('+esc(t('spool_n',{id:u.id}))+')</td>'+
      V.map(v=>'<td><input type="text" list="presets" data-map="'+esc(u.key)+'" data-v="'+esc(v)+'" placeholder="'+esc(v==='default'?t('col_variant_default'):t('col_variant',{nozzle:v}))+'"></td>').join('')+'</tr>';});
    h+='</table>';
  }
  h+='<div class="row" style="margin-top:8px"><button id="b-sync-ok">'+esc(t('sync_apply'))+'</button><button class="sec" id="b-sync-no">'+esc(t('sync_discard'))+'</button></div>';
  box.innerHTML=h;
  $('b-sync-ok').onclick=()=>{const map={};box.querySelectorAll('[data-map]').forEach(el=>{
      const k=el.dataset.map;map[k]=map[k]||{};if(el.value.trim())map[k][el.dataset.v]=el.value.trim();});
    send({cmd:'sync_apply',map:map});};
  $('b-sync-no').onclick=()=>send({cmd:'sync_discard'});
}
$('rows').addEventListener('input',e=>{const el=e.target,i=+el.dataset.i;if(isNaN(i))return;
  if(el.dataset.v){slots[i].presets=slots[i].presets||{};slots[i].presets[el.dataset.v]=el.value;}else slots[i][el.dataset.k]=el.value;});
$('rows').addEventListener('click',e=>{const b=e.target.closest('[data-a]');if(!b)return;const i=+b.dataset.i;
  if(b.dataset.a==='del')slots.splice(i,1);
  else{const j=b.dataset.a==='up'?i-1:i+1;if(j<0||j>=slots.length)return;[slots[i],slots[j]]=[slots[j],slots[i]];}
  render();});
$('plist').addEventListener('change',e=>{const el=e.target;
  if(el.dataset.p){if(el.checked)printers[el.dataset.p]='';else delete printers[el.dataset.p];renderPrinters();}
  else if(el.dataset.pn)printers[el.dataset.pn]=el.value.trim();});
$('pfilter').oninput=renderPrinters;
$('b-add').onclick=()=>{slots.push({presets:{'default':''},color:'#FFFFFF',spool:null});render();};
$('b-save').onclick=()=>send({cmd:'save_std',std:collect()});
$('b-live').onclick=()=>send({cmd:'restore_live'});
// >>> full-edition
$('b-full').onclick=()=>{if(confirm(t('full_confirm')))send({cmd:'restore_full',relaunch:$('relaunch').checked});};
$('b-cancel').onclick=()=>send({cmd:'cancel_full'});
$('confedit').onchange=()=>send({cmd:'save_std',std:collect()});
// <<< full-edition
$('b-capture').onclick=()=>{if(confirm(t('capture_confirm')))send({cmd:'capture'});};
$('b-sync').onclick=()=>{const u=$('url').value.trim(),o=origin(u);
  if(o&&S.std.spoolman_consent!==o){if(!confirm(t('spoolman_confirm',{url:o})))return;
    send({cmd:'save_std',std:collect()});send({cmd:'sync_preview',consent:true});return;}
  send({cmd:'sync_preview'});};
$('b-prices').onclick=()=>send({cmd:'apply_prices'});
$('b-addprinter').onclick=()=>send({cmd:'add_current_printer'});
$('b-reset').onclick=()=>{if(confirm(t('reset_confirm')))send({cmd:'reset'});};
$('b-export').onclick=()=>{const j=$('json');j.style.display='';j.value=JSON.stringify(collect(),null,1);};
$('b-import').onclick=()=>{const j=$('json');if(j.style.display==='none'){j.style.display='';j.value='';j.focus();return;}send({cmd:'import_json',text:j.value});};
['auto','lang','sortsync'].forEach(id=>$(id).onchange=()=>send({cmd:'save_std',std:collect()}));
orca.onMessage(msg=>{
  if(!msg)return;
  if(msg.type==='state'){S=msg;T=msg.i18n||{};slots=JSON.parse(JSON.stringify(msg.std.slots));printers=JSON.parse(JSON.stringify(msg.std.printers||{}));render();}
  else if(msg.type==='refresh_request')send({cmd:'ready'});
  else if(msg.type==='auto_request')send({cmd:'restore_live'});
});
send({cmd:'ready'});
</script></body></html>"""


def main(argv):
    # >>> full-edition
    if len(argv) >= 3 and argv[1] == "--apply":
        return run_job(argv[2])
    if len(argv) >= 4 and argv[1] == "--restore":
        if orca_running():
            print("Close OrcaSlicer first.")
            return 2
        std = clean_standard(read_json(argv[3]) or {})
        restore(argv[2], std)
        return 0
    if len(argv) >= 4 and argv[1] == "--undo":
        if orca_running():
            print("Close OrcaSlicer first.")
            return 2
        undo(argv[2], argv[3])
        return 0
    print("usage:\n  python filament_standard.py --apply <job.json>\n"
          "  python filament_standard.py --undo <OrcaSlicer data dir> <backup folder>\n"
          "  python filament_standard.py --restore <OrcaSlicer data dir> <standard.json>")
    return 1
    # <<< full-edition
    print("FilamentStandard %s (%s edition) is an OrcaSlicer plugin: install it from OrcaSlicer's plugin manager." % (VERSION, EDITION))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
