# MiniMonitor C15M

Dashboard de 240×240 para a minitela do **Positivo Vision C15M**. Mostra relógio, CPU, RAM, bateria, temperatura da CPU e Wi-Fi. As métricas são coletadas localmente e atualizadas a cada dois segundos.

Testado em um C15M (C4128B-15, placa P15X) com Arch Linux, USB CDC 0324:0324 e protocolo AHMI. O painel físico foi testado com tema estático e dinâmico. O serviço de inicialização automática também foi testado nesse notebook. A compatibilidade com outras revisões ainda precisa ser verificada.

## Prévia no desktop

No Arch, instale Python 3 e os pacotes **python-psutil**, **python-cairo**, **python-gobject** e **gtk4**. A partir da raiz do projeto:

```sh
python -m minimonitor
```

Para gerar um PNG de 240×240:

```sh
python -m minimonitor --png dashboard.png
```

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

A distribuição inclui o código do projeto. O compilador, o tema de fábrica e o tema compilado a partir dos recursos da Policorp são obtidos ou gerados localmente. O gravador aceita os SHA-256 dos temas verificados no notebook de referência. Se outra compilação gerar um hash diferente, ela exige validação separada antes de qualquer gravação. Gravar um ACF substitui o tema ativo. Confirme a revisão da minitela e tenha um tema compatível para restauração antes desse passo.

Depois de instalar o tema dinâmico:

```sh
python -m minimonitor --mostrar-dashboard
python -m minimonitor --atualizar-dashboard
```

O primeiro comando seleciona a página 5. O segundo envia os campos alterados em memória até você pressionar Ctrl+C.

### Iniciar com o notebook

Os exemplos em **deploy/** iniciam o dashboard antes do login em um sistema com systemd. Salve cópias sem o sufixo **.example** e preencha **@USERNAME@**, **@PROJECT_DIR@** e **@USB_ID_PATH@** com seu usuário, caminho absoluto do projeto e caminho USB da minitela. Para ver **ID_PATH**, consulte **udevadm info --query=property --name=/dev/ttyACM0** e ajuste o nome da porta conforme o diagnóstico.

Instale a regra em **/etc/udev/rules.d/** e o serviço em **/etc/systemd/system/**. A regra usa **setfacl** do pacote **acl** para dar acesso somente à porta identificada. Habilite o serviço com **sudo systemctl daemon-reload** e **sudo systemctl enable minimonitor-c15m.service**. O serviço passa a iniciar no próximo boot.

## Referências

- [Engenharia reversa do protocolo AHMI e do formato ACF](https://github.com/caio-imperial/minitela-r15)
- [Primeiros testes de controle da minitela no C15M e no R15M](https://github.com/rpelicia/open-minitela-R15M)
