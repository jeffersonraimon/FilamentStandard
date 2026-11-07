<p align="center"><img src="assets/icon.svg" width="160" alt="FilamentStandard"></p>

# FilamentStandard

**Mantenha uma lista padrão de filamentos para as suas impressoras no OrcaSlicer: mesma ordem, mesmas cores e o perfil certo para cada bico. Restaure a lista depois de abrir projetos de outras pessoas e sincronize carretéis e preços com o [Spoolman](https://github.com/Donkie/Spoolman).**

[Read in English](README.md)

[![CI](https://github.com/jeffersonraimon/FilamentStandard/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jeffersonraimon/FilamentStandard/actions/workflows/ci.yml)

> Plugin Python para o OrcaSlicer **2.5+**. É um arquivo só, `filament_standard.py`, e não tem dependências.

## Por quê

O OrcaSlicer guarda uma lista de filamentos por perfil de impressora, em `orca_presets` dentro do `OrcaSlicer.conf`. Duas coisas bagunçam essa lista:

- Cada perfil tem a sua própria lista. Ao trocar do bico 0.4 para o 0.2, os slots deixam de bater e as cores trocam de lugar.
- Abrir um projeto `.3mf` substitui a lista do perfil ativo pelos filamentos do projeto. Os que você não tem viram "Generic PLA" ou "Bambu PLA Basic", e o próximo *Novo projeto* continua com essa lista.

O FilamentStandard guarda uma lista padrão: slot → perfil de filamento por diâmetro de bico, cor e carretel do Spoolman. Ele devolve essa lista quando você quiser.

## Recursos

| | |
|---|---|
| **Editor da lista padrão** | Uma aba com uma linha por slot: cor, perfil para cada diâmetro de bico (a coluna *padrão* vale quando o bico não tem perfil próprio), carretel do Spoolman e o que o projeto atual tem naquele slot. |
| **Usar a lista atual como padrão** | Captura os slots e as cores do projeto aberto. Os carretéis são mantidos casando perfil e cor. |
| **Restaurar perfis agora** | Troca na hora o perfil de cada slot existente, pela API de plugins. |
| **Restauração completa ao fechar** | Um pequeno auxiliar espera o OrcaSlicer fechar e faz o que a API não consegue: grava a lista (perfis, cores e matriz de purga) em **todos os perfis de impressora escolhidos** e os preços nos perfis de filamento. Antes, faz backup de tudo. Depois, pode reabrir o OrcaSlicer. |
| **Sincronização com o Spoolman** *(opcional)* | Mostra antes os carretéis novos e removidos, as mudanças de cor e o preço médio por kg de cada perfil. Só aplica quando você confirma. Carretel de filamento desconhecido pede o perfil uma vez e lembra dele. |
| **Restaurar ao criar Novo projeto** *(opcional, desligado por padrão)* | Troca os perfis sempre que um projeto novo começa. |
| **Qualquer impressora** | Bambu Lab, Prusa, Creality, Voron/Klipper e outras. O perfil é escolhido por diâmetro de bico, e impressoras com mais de um extrusor mantêm uma matriz de purga por extrusor. |
| **English / Português** | Segue o idioma do OrcaSlicer, ou você escolhe em Configuração. |
| **Importar / exportar** | Copie o padrão em JSON para compartilhar ou versionar. |

### O que a API de plugins faz e o que não faz

A API do OrcaSlicer 2.5 consegue trocar o perfil de um slot **que já existe** (`orca.host.preset.filament.begin_update`). Ela não cria nem remove slots e não muda a cor de um slot. Por isso existe a **restauração completa**: ela edita o `OrcaSlicer.conf` com o OrcaSlicer fechado, do mesmo jeito que o próprio OrcaSlicer grava o arquivo, com checksum MD5.

## Instalação

1. Baixe o [`filament_standard_any.py`](https://github.com/jeffersonraimon/FilamentStandard/releases/latest/download/filament_standard_any.py), ou assine o **FilamentStandard** no Orca Cloud quando ele estiver publicado.
2. No OrcaSlicer, abra **Plugins** → *More plugin install options* → **Install local plugin** e escolha o arquivo.
3. Aceite os pedidos de permissão:
   - **threads**: para a restauração ao vivo;
   - **rede**: só para o host do Spoolman que você configurar;
   - **executar programa**: para o auxiliar da restauração completa.
4. Aparece uma aba nova, **FilamentStandard**.

**Requisito da restauração completa:** um Python 3 no `PATH`, porque o auxiliar roda fora do OrcaSlicer:

| Sistema | Interpretador usado |
|---|---|
| Windows | `pythonw`, `pyw`, `python` ou `py` |
| macOS / Linux | `python3` |

Todo o resto roda no Python embutido do OrcaSlicer.

## Primeiros passos

1. Monte num projeto os filamentos e as cores que você quer, na ordem de sua preferência.
2. Clique em **Usar a lista atual como padrão**.
3. Em **Perfis de impressora**, marque todos os perfis de impressora ou de bico que devem compartilhar a lista. O diâmetro do bico é lido do perfil. Preencha a coluna `0.2 mm` (ou outra) nos filamentos que têm perfil específico para aquele bico.
4. Clique em **Salvar padrão**.
5. Sempre que um projeto bagunçar a lista:
   - **Restaurar perfis agora** corrige os perfis dos slots existentes;
   - **Restauração completa ao fechar**, seguida de fechar o OrcaSlicer, corrige tudo, inclusive cores e quantidade de slots.

### Spoolman

Em **Configuração**, informe a URL do Spoolman, por exemplo `http://192.168.1.10:7912`, e use **Sincronizar com o Spoolman**.

- Cada carretel é ligado a um slot pelo ID, que aparece na coluna *Carretel*.
- Com **ordenar ao sincronizar** ligado, a lista fica assim: PLA branco, PLA preto, demais PLA por marca, PETG branco, PETG preto, demais PETG e depois os outros materiais.
- O preço de cada perfil é a média de `preço / peso inicial` dos carretéis ativos dele. Ele é gravado no *custo do filamento* do perfil na próxima restauração completa.

## Onde ficam os dados

| O quê | Onde |
|---|---|
| Lista padrão e configurações | `<pasta de dados do OrcaSlicer>/orca_plugins/plugin_data/<plugin>/standard.json` |
| Restauração completa pendente | `job.json`, na mesma pasta |
| Log do auxiliar | `apply.log`, na mesma pasta |
| Backups (um por restauração completa) | `<pasta de dados do OrcaSlicer>/backup-filament-standard-<data>/`, com o `OrcaSlicer.conf` e os perfis de filamento |

A pasta de dados do OrcaSlicer é `%APPDATA%\OrcaSlicer` no Windows, `~/Library/Application Support/OrcaSlicer` no macOS e `~/.config/OrcaSlicer` no Linux.

**Migração da versão anterior:** se você usava o plugin antigo "Filamentos Padrão", a lista dele (`plugin_data/filamentos_padrao/padrao.json`) é importada automaticamente na primeira vez que a aba abre.

### Linha de comando

Com o OrcaSlicer fechado, o mesmo arquivo restaura um padrão sem a interface:

```bash
python filament_standard.py --restore "<pasta de dados do OrcaSlicer>" standard.json
```

## Como funciona

- **Restauração ao vivo:** para cada slot com perfil diferente, chama `orca.host.preset.filament.begin_update(slot, perfil).commit()` numa thread de trabalho, como a API exige.
- **Restauração completa:**
  - grava o `job.json` e inicia `python filament_standard.py --apply job.json` em segundo plano;
  - o auxiliar espera até não haver nenhum processo do OrcaSlicer e lê o `standard.json` **mais recente**;
  - em cada perfil de impressora escolhido, reescreve `filament`, `filament_NN`, `filament_colors`, `filament_multi_colors`, `filament_color_types` e as chaves por slot, além da matriz e do vetor de purga;
  - grava o arquivo exatamente como o OrcaSlicer (indentação com tab, UTF-8 sem escape, `# MD5 checksum` do texto em LF).
- **Volumes de purga:** a fórmula `FlushVolCalc` do OrcaSlicer, que é baseada na cor, portada para Python, mais uma purga mínima de 92 mm³. Você sempre pode clicar em *Recalcular* no diálogo de volumes de purga do OrcaSlicer.
- **Preços:** vão para o `filament_cost` em `user/<id>/filament/<perfil>.json`. O `.info` é marcado com `sync_info = update`, para o OrcaSlicer enviar a mudança se você usa sincronização na nuvem.

## Desenvolvimento

```bash
python -m pip install pytest ruff
python -m pytest          # testes unitários e de integração, com um OrcaSlicer falso
python -m ruff check .
```

- **CI:** roda no Windows, macOS e Linux, com Python 3.10 a 3.13.
- **Releases:** uma tag `vX.Y.Z` igual ao `VERSION` publica o `filament_standard.py` numa release do GitHub.
- **Contribuições:** veja [CONTRIBUTING.md](CONTRIBUTING.md).
- **Orca Cloud:** veja [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Licença

[MIT](LICENSE) © Jefferson J. Raimon
