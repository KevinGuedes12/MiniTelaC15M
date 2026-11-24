# MiniMonitor C15M

Dashboard de 240×240 para a minitela do **Positivo Vision C15M**. Mostra relógio, CPU, RAM, bateria, temperatura da CPU e Wi-Fi. As métricas são coletadas localmente e atualizadas a cada dois segundos. A página **Música** detecta players MPRIS e mostra faixa, artista, progresso e um visualizador decorativo. Ao iniciar uma reprodução, a minitela muda para Música. Após 30 segundos sem reprodução ativa, volta ao Dashboard.

![Prévia de 240×240 da página Música com barras decorativas](docs/visualizador.png)

Testado em um C15M (C4128B-15, placa P15X) com Arch Linux, USB CDC 0324:0324 e protocolo AHMI. O painel físico foi testado com tema estático e dinâmico. O tema com Música, as teclas dedicadas e o início automático também foram testados nesse notebook. A compatibilidade com outras revisões ainda precisa ser verificada.

## Compatibilidade

| Modelo Vision | Evidência |
| --- | --- |
| C15M (C4128B-15, P15X) | Tema dinâmico e início automático testados neste projeto. |
| R15M | USB 0324:0324 e protocolo AHMI documentados por outro projeto. O tema MiniMonitor e a tecla dedicada ainda precisam de teste. |
| i15M, N15M e P15M | Minitela anunciada pela Positivo. Transporte, revisão e comportamento da tecla ainda precisam de validação. |

A aparência da minitela e a correspondência do identificador USB são insuficientes para validar uma gravação de tema em outro modelo. Para confirmar uma variante, comece por `python -m minimonitor --hardware`. Ele mostra modelo e placa DMI, porta e revisão USB sem abrir a serial. Compartilhe esses dados para identificar a revisão. A confirmação do protocolo, do tema e da tecla exige testes próprios.

## Prévia no desktop

No Arch, instale Python 3 e os pacotes **python-psutil**, **python-cairo**, **python-gobject** e **gtk4**. A partir da raiz do projeto:

```sh
python -m minimonitor
```

Para gerar um PNG de 240×240:

```sh
python -m minimonitor --png dashboard.png
```

## Música e atalhos

Abra a prévia com **python -m minimonitor --preview-musica** dentro da sessão gráfica. O player precisa publicar dados via MPRIS. A prévia pode exibir a capa do álbum, com cache local em memória. A minitela física usa as barras decorativas, que se movem enquanto a reprodução está ativa. Nenhuma entrada de áudio é necessária.

| Atalho | Ação |
| --- | --- |
| MINITELA | Alterna entre Dashboard e Música quando há mídia disponível |
| MINITELA + ← | Faixa anterior |
| MINITELA + → | Próxima faixa |
| MINITELA + Espaço | Pausa ou retoma |

No C15M testado, MINITELA chegou como **EV_KEY 186 (F16)**. O código e o caminho do teclado podem variar. **python -m minimonitor.media_keys /dev/input/eventN** reconhece a primeira tecla pressionada em um dispositivo que o usuário possa ler. O programa não impede que as setas e o espaço também cheguem ao aplicativo em foco.

## Minitela física

```sh
python -m minimonitor --hardware
```

Esse comando lê metadados e identifica a porta. Quando o usuário tiver acesso à porta, **--minitela-status** pode consultar o estado AHMI sem alterar a página ou gravar dados.

Para o painel completo, o módulo precisa de um tema que desenhe os elementos de interface. O tema é gravado uma vez na região de temas da minitela. Depois, o atualizador usa só USB serial e Python. O Wine é necessário para compilar o tema com a ferramenta do fabricante.

### Gerar o tema localmente

1. Obtenha o pacote original **Minitela 1.0.20** da Policorp. Extraia os recursos sem instalar o pacote. Você precisará do projeto **resources/ACF/file.zip**, das imagens originais e do compilador que está no **MiniPanel-0.1.6.AppImage**. [Referência ao pacote](https://plus.diolinux.com.br/t/mini-tela-da-positivo-no-linux/76478/176)
2. Prepare uma cópia do ZIP principal com os três slots GIF de 240×240 reduzidos a um quadro cada. Use os nomes originais presentes no ZIP. O fluxo de referência documenta os nomes e a conversão das imagens. [Geração de temas AHMI](https://github.com/caio-imperial/minitela-r15/blob/main/minitela_build.py)
3. Execute **python -m minimonitor.live_theme base.zip dinamico.zip**. O gerador substitui a primeira página de imagens pelo dashboard com oito campos de texto e duas barras.
4. No diretório **resources/IDE_utils/Gen** extraído do AppImage, rode o compilador com o Wine, passando os caminhos absolutos do ZIP e de um diretório de saída novo:

   ```sh
   printf 13 | wine ./AHMISimGenDemo_og.exe -f /caminho/dinamico.zip -m 2 -c 0 -e 0 -d 1 -o /caminho/saida
   ```

Para o tema com Dashboard, Música e barras, os scripts abaixo fazem esse preparo e a compilação. Passe um diretório de trabalho novo e o pacote original que você obteve no passo 1. Os scripts pedem **binutils** (ar), **libarchive** (bsdtar), **FFmpeg** e **Wine** para preparar e compilar.

```bash
bash tools/preparar-tema-musica.sh /caminho/minitela_1.0.20_amd64.deb ./build
bash tools/compilar-tema-musica.sh ./build
```

A distribuição inclui o código do projeto. O compilador, o tema de fábrica e o tema compilado a partir dos recursos da Policorp são obtidos ou gerados localmente. O gravador aceita os SHA-256 dos temas verificados no notebook de referência. Se outra compilação gerar um hash diferente, ela exige validação separada antes de qualquer gravação. Gravar um ACF substitui o tema ativo. Confirme a revisão da minitela e tenha um tema compatível para restauração antes desse passo.

Depois de instalar o tema dinâmico:

```sh
python -m minimonitor --mostrar-dashboard
python -m minimonitor --atualizar-dashboard
```

O primeiro comando seleciona a página 5. O segundo envia os campos alterados em memória até você pressionar Ctrl+C.

Para o tema com Música e barras, execute na sessão do KDE, GNOME ou outro desktop:

```bash
python -m minimonitor --atualizar-com-musica --visualizador \
  --input-device /dev/input/by-path/platform-i8042-serio-0-event-kbd --minitela-key 186
```

O caminho e o código do exemplo são os observados no C15M de referência. Os parâmetros de teclado são opcionais. Pare qualquer outra instância ou serviço MiniMonitor antes do teste. Um único gerenciador mantém a porta serial aberta e alterna as páginas.

### Iniciar com o notebook

Os exemplos em **deploy/** iniciam o dashboard antes do login em um sistema com systemd. Salve cópias sem o sufixo **.example** e preencha **@USERNAME@**, **@PROJECT_DIR@** e **@USB_ID_PATH@** com seu usuário, caminho absoluto do projeto e caminho USB da minitela. Para ver **ID_PATH**, consulte **udevadm info --query=property --name=/dev/ttyACM0** e ajuste o nome da porta conforme o diagnóstico.

Instale a regra em **/etc/udev/rules.d/** e o serviço em **/etc/systemd/system/**. A regra usa **setfacl** do pacote **acl** para dar acesso somente à porta identificada. Habilite o serviço com **sudo systemctl daemon-reload** e **sudo systemctl enable minimonitor-c15m.service**. O serviço passa a iniciar no próximo boot.

Para incluir Música e os atalhos no boot, adapte também **deploy/73-minimonitor-c15m-tecla.rules.example** e **deploy/musica.conf.example**. Preencha o nome de usuário, ID_PATH do teclado, caminho do dispositivo e código da tecla. Instale a regra em **/etc/udev/rules.d/73-minimonitor-c15m-tecla.rules** e o complemento em **/etc/systemd/system/minimonitor-c15m.service.d/musica.conf**. Depois de **sudo systemctl daemon-reload**, reinicie. O complemento mantém o dashboard antes do login e conecta ao MPRIS quando o barramento do usuário fica disponível. A regra concede leitura ao teclado escolhido para permitir os atalhos.

## Testes

```bash
python -m unittest discover -s tests
```

Os testes simulam sinais MPRIS, troca de páginas, atalhos e envio AHMI. O serviço do notebook usa GIO e deixa GDK e GTK para a prévia. Em teste curto com USB simulada, o processo ocupou cerca de 32 MiB de RAM.

## Referências

- [Engenharia reversa do protocolo AHMI e do formato ACF](https://github.com/caio-imperial/minitela-r15)
- [Primeiros testes de controle da minitela no C15M e no R15M](https://github.com/rpelicia/open-minitela-R15M)
