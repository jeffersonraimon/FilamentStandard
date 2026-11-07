# Publishing / Publicação

## GitHub
1. Push the repository to `https://github.com/jeffersonraimon/FilamentStandard`.
2. Tag a release: `git tag v2.0.0 && git push origin v2.0.0`.
3. The CI workflow checks that the tag matches `VERSION` and attaches `filament_standard.py` to the release.
4. Users install the downloaded file with **Plugins → Install local plugin**.

## Orca Cloud
OrcaSlicer 2.5 lets users subscribe to plugins published on Orca Cloud (<https://cloud.orcaslicer.com>). Subscribed plugins are installed under `orca_plugins/_subscribed/<user>/<plugin-id>/` and update when the author publishes a new version. At the time of writing there is no public developer guide for submitting plugins, so check the Orca Cloud site and the OrcaSlicer wiki ("Plugin development guide", linked from the 2.5.0 release notes) for the current flow.

What Orca Cloud reads from the plugin file:
- The PEP 723 header with `[tool.orcaslicer.plugin]`: `id`, `name`, `description`, `author` and `version`. Keep `version` in sync with `VERSION`; it is what triggers the update for subscribers.
- `dependencies = []`: keep it empty.

Checklist before uploading a new version:
- [ ] `python -m pytest` passes
- [ ] the version is bumped in both places
- [ ] the plugin was tested once in OrcaSlicer: live restore, full restore and Spoolman sync
- [ ] the GitHub release exists, so the cloud listing can link to the source

---

### Português (resumo)
- **GitHub:** crie a tag `vX.Y.Z` e faça push dela. O CI confere a versão e anexa o `filament_standard.py` à release.
- **Orca Cloud:**
  - entre em <https://cloud.orcaslicer.com> com a sua conta e envie o `filament_standard.py`;
  - o cabeçalho `[tool.orcaslicer.plugin]` define nome, descrição, autor e versão;
  - para atualizar quem já assinou, aumente a versão e envie o arquivo de novo;
  - ainda não há um guia público para desenvolvedores, então confira o fluxo atual no site.
