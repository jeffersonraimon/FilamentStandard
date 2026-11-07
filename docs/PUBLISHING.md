# Publishing / Publicação

## File name

Orca Cloud requires the plugin file name to end with a **target suffix** before `.py` or `.whl`. FilamentStandard is pure Python and runs everywhere, so it is published as **`filament_standard_any.py`**.

The accepted suffixes are:

| Target | Suffixes |
|---|---|
| Every OS and architecture | `any` |
| Windows | `win`, `win_x86_64`, `win_arm64` |
| macOS | `macosx`, `macosx_x86_64`, `macosx_arm64`, `macosx_universal` |
| Linux | `linux`, `linux_x86_64`, `linux_arm64` |

The source file in the repository stays `filament_standard.py`. `scripts/build_release.py` creates two editions in `dist/`:

| File | Edition | Contents |
|---|---|---|
| `filament_standard_any.py` | Cloud, for Orca Cloud | Every block between `>>> full-edition` and `<<< full-edition` is removed. It uses only the plugin API and its own storage folder, which is what Orca Cloud's automated review requires. `tests/test_cloud_edition.py` checks it. |
| `filament_standard.py` | Full, for GitHub releases | Keeps the opt-in full restore. |

Code that reads `OrcaSlicer.conf` or user preset files, or starts processes, must stay inside those markers.

## Releasing a new version

1. Bump `VERSION` and the `# version =` header in `filament_standard.py`.
2. Add a `## [X.Y.Z]` section to `CHANGELOG.md`, then commit and push.
3. **Publish a GitHub release**: a tag alone is not enough. With the GitHub CLI:

   ```bash
   python scripts/build_release.py vX.Y.Z      # checks the version, writes dist/notes.md
   gh release create vX.Y.Z --title "FilamentStandard X.Y.Z" --notes-file dist/notes.md
   ```

   You can also use *Releases → Draft a new release* on GitHub.
4. Publishing the release runs `.github/workflows/publish-orcacloud.yml`, which:
   - runs the tests;
   - builds both editions and attaches them to the release;
   - **if `ORCACLOUD_PUBLISH` is `true`**, uploads `filament_standard_any.py` to Orca Cloud as version `X.Y.Z`, with the release notes as the changelog.

**Notes**
- **Why a published release:** Orca Cloud only accepts the OIDC token of a connected workflow that runs on `release: published`.
- **Who must create the release:** a person, or the `gh` CLI with your own login. A release created by `GITHUB_TOKEN` inside another workflow does not trigger workflows.
- **Version check:** Orca Cloud rejects a version that is not greater than the current one.

## Orca Cloud: one-time setup

1. **Create the plugin.** At <https://cloud.orcaslicer.com>, go to *Shared Plugins* and create a plugin:
   - upload `filament_standard_any.py`, from the latest GitHub release or from `dist/` after `python scripts/build_release.py vX.Y.Z`;
   - set the version to the current one, the *Type* (Pages), the minimum OrcaSlicer version (2.5.0) and a description;
   - optionally add the image `assets/icon-512.png` (PNG, under 2 MB).
2. **Connect the repository.** In *Edit plugin* → *GitHub publishing*, enter `jeffersonraimon/FilamentStandard` and click **Connect**. This grants Orca Cloud no access to the repository; it only lets this repository's workflows publish versions of this plugin.
3. **Turn on publishing from CI:**

   ```bash
   gh variable set ORCACLOUD_PUBLISH --body true --repo jeffersonraimon/FilamentStandard
   ```

**Notes**
- **Authentication:** it uses a short-lived GitHub OIDC token (`id-token: write`), so no secrets are stored.
- **Errors:**
  - `401`: the repository is not connected to exactly one of your plugins.
  - version error: the tag is not greater than the version already on Orca Cloud.
- **Re-running:** re-running a successful release is safe; Orca Cloud rejects the duplicate without side effects.

---

## Português

**Nome do arquivo**
- O Orca Cloud exige um sufixo de plataforma antes de `.py` ou `.whl`. Como o plugin é Python puro, ele é publicado como **`filament_standard_any.py`** (`any` = qualquer sistema e arquitetura).
- No repositório, o arquivo continua `filament_standard.py`.

**Nova versão**
1. Atualize o `VERSION`, o cabeçalho `# version =` e o `CHANGELOG.md`, depois faça commit e push.
2. Publique uma release (só a tag não basta):
   `python scripts/build_release.py vX.Y.Z && gh release create vX.Y.Z --title "FilamentStandard X.Y.Z" --notes-file dist/notes.md`
3. O workflow `publish-orcacloud.yml`:
   - testa o código;
   - anexa as duas edições à release;
   - com `ORCACLOUD_PUBLISH=true`, envia a edição Cloud ao Orca Cloud.

**Primeira vez no Orca Cloud**
1. Em *Shared Plugins*, crie o plugin enviando o `filament_standard_any.py`. A imagem pode ser o `assets/icon-512.png`.
2. Em *Edit plugin* → *GitHub publishing*, conecte o repositório `jeffersonraimon/FilamentStandard`.
3. Rode `gh variable set ORCACLOUD_PUBLISH --body true`.
