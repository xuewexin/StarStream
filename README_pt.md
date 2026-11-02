<div align="center">

<p align="center">
  <b>Language / Multilíngue:</b><br>
  <a href="README.md">简体中文</a> •
  <a href="README_zh-TW.md">繁體中文</a> •
  <a href="README_en.md">English</a> •
  <a href="README_ja.md">日本語</a> •
  <a href="README_ko.md">한국어</a> •
  <a href="README_fr.md">Français</a> •
  <a href="README_de.md">Deutsch</a> •
  <a href="README_es.md">Español</a> •
  <a href="README_ru.md">Русский</a> •
  <a href="README_pt.md">Português</a>
</p>

<p align="center">
  <img src="docs/images/starstream_logo.png" width="128" height="128" alt="StarStream Logo">
</p>

# 🌟 StarStream Pro - Baixador de Mídia

**Extensão de captura de áudio e vídeo da Web tudo-em-um + Cliente de download multithread industrial + Núcleos N_m3u8DL-RE e FFmpeg integrados**

[![GitHub Release](https://img.shields.io/github/v/release/xuewexin/StarStream?style=flat-square&color=blue&label=GitHub%20Release)](https://github.com/xuewexin/StarStream/releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d7.svg?style=flat-square&logo=windows)](#)
[![Python](https://img.shields.io/badge/Python-3.8%20~%203.13-3776ab.svg?style=flat-square&logo=python)](#)
[![UI Framework](https://img.shields.io/badge/UI-PyQt5%20%7C%20Dark%20Slate-6366f1.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-MIT-emerald.svg?style=flat-square)](#)

<br>

<p align="center">
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.1.2/StarStream_v3.1.2_Portable.zip">
    <img src="https://img.shields.io/badge/⬇️%20Cliente%20Desktop-StarStream_v3.1.2_Portable.zip%20(Núcleo%20Integrado)-2563eb?style=for-the-badge&logo=windows&logoColor=white" alt="Baixar StarStream.exe">
  </a>
  &nbsp;&nbsp;
  <a href="https://github.com/xuewexin/StarStream/releases/download/v3.1.2/StarStream_Browser_Extension_v3.1.2.zip">
    <img src="https://img.shields.io/badge/🧩%20Extensão%20para%20Navegador-Extension.zip%20(Apenas%20140KB)-059669?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Baixar Extensão para Navegador">
  </a>
</p>

> [!IMPORTANT]
> ### 💡 Guia da Dupla Perfeita: Software Desktop e Extensão trabalhando em equipe!
> - **🧩 Extensão de Captura (Radar Front-end)**: Intercepta e extrai automaticamente fluxos reais M3U8, DASH (MPD) e MP4 durante a navegação, exibindo uma cápsula suspensa sobre o player de vídeo;
> - **💻 Cliente Desktop (Motor Back-end)**: Recebe tarefas enviadas pela extensão e utiliza os motores integrados **N_m3u8DL-RE** e **FFmpeg** para downloads concorrentes de alta velocidade (até 24.7 MB/s) e mesclagem sem perdas;
> - **Sinergia Total (como o IDM e sua extensão)**: Ambos são indispensáveis. Siga as instruções no [Guia de Instalação da Extensão](#-guia-de-instalação-da-extensão-no-navegador).

<p align="center">
  <a href="#-demonstração-e-capturas">Demonstração</a> •
  <a href="#-versões-e-downloads">Downloads</a> •
  <a href="#-recursos-principais">Recursos</a> •
  <a href="#-guia-de-instalação-da-extensão-no-navegador">Instalação</a> •
  <a href="#-perguntas-frequentes-faq">FAQ</a> •
  <a href="#-isenção-de-responsabilidade">Isenção</a>
</p>

</div>

---

## 📸 Demonstração e Capturas

### 1. Painel principal de controle (Design moderno Dark Slate)
> Ícones vetoriais nítidos e monitoramento total de status: porta local `18910` pronta, módulo `FFmpeg` pronto, motor `N_m3u8DL (RE)` ativo e indicador de proxy em tempo real.

<p align="center">
  <img src="docs/images/app_main_window.png" width="92%" alt="Captura de tela do painel principal">
</p>

---

### 2. Nova tarefa de download (Configuração individual de proxy e threads)
> Análise e extração profunda de links com um único clique. Configure o número de threads (4 a 32), diretório exclusivo e modo de proxy de rede por tarefa.

<p align="center">
  <img src="docs/images/app_new_task.png" width="82%" alt="Diálogo de nova tarefa">
</p>

---

### 3. Caixa de ferramentas multimídia FFmpeg (Conversão e pós-processamento)
> Estação de trabalho multimídia pronta para uso: conversão individual e em lote (MP4/MKV/TS/MOV), mesclagem de áudio/vídeo, extração de áudio sem perdas e corte rápido.

<p align="center">
  <img src="docs/images/app_ffmpeg_toolbox.png" width="82%" alt="Ferramentas FFmpeg">
</p>

---

### 4. Captura contínua de streams internacionais (Exemplo YouTube)
> Um selo flutuante elegante aparece discretamente durante a reprodução. Exibe resolução real, duração e transfere a tarefa diretamente pelo mesmo canal proxy.

<p align="center">
  <img src="docs/images/web_capsule_youtube.png" width="82%" alt="Cápsula de captura do YouTube">
</p>

---

### 5. Captura inteligente de vídeo da web e envio direto (Alinhamento de proxy)
> Exibe resoluções reais, duração e formato. Alinha-se automaticamente ao proxy do navegador para downloads ultrarrápidos no cliente de desktop.

<p align="center">
  <img src="docs/images/web_capsule_bilibili.png" width="58%" alt="Cartão flutuante do capturador web">
</p>

---

### 6. Monitoramento de tarefas e central de ferramentas rápidas
> Clique no orbe flutuante para expandir o painel: veja downloads em andamento, velocidade global e inicie o conversor, a caixa FFmpeg ou o extrator de vídeo.

<p align="center">
  <img src="docs/images/app_floating_panel.png" width="68%" alt="Painel de monitoramento e ferramentas">
</p>

---

### 7. Widget flutuante de desktop (Monitoramento em tempo real de tarefas e velocidade)
> Widget interativo em formato de planeta com suporte a arrastar pelo desktop, fixação nas bordas e acompanhamento dinâmico das tarefas e taxa de transferência.

<p align="center">
  <img src="docs/images/app_floating_widget.png" width="28%" alt="Widget flutuante de desktop">
</p>


## ⚡ Recursos Principais

| Módulo | Descrição |
|---|---|
| **Capturador Universal** | Suporta M3U8 (HLS), MPD (DASH), MP4, FLV, WebM, TS, MP3, AAC e links diretos. Interceptação profunda em `HTMLMediaElement.play`, `Blob`, `MediaSource`, `fetch/XHR`. |
| **Cápsula Flutuante** | Botão inserido no player identificando resoluções (4K/1080P/720P), duração e fluxos de áudio separados. |
| **Player Integrado** | Player leve `hls.min.js` no popup da extensão para pré-visualização de streams antes de baixar. |
| **Dois Motores de Download** | **Streaming**: [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) para download de segmentos e multiplexação.<br>**Link Direto**: Baixador Range multithread nativo em Python. |
| **Configuração por Vídeo** | Diretório individual, quantidade de threads (4/8/16/32) e proxy exclusivo para cada vídeo. |
| **Alinhamento de Proxy** | Sincroniza o IP de saída do baixador com o do navegador para evitar erros HTTP 403 Forbidden. |
| **Conversor de Formatos** | Conversão em lote: cópia sem perdas (`-c copy`), reencodificação H.264/H.265 e extração de áudio de alta fidelidade. |
| **Notificações Desktop** | Popups no canto inferior direito ao concluir ou falhar downloads com botões de ação rápida. |
| **Conversão para MP4** | Invocação automática do FFmpeg para remuxing em MP4 com metadados `faststart`. |
| **Diagnóstico Inteligente** | Registra e analisa erros em `Logs/download_errors.log` com sugestões diretas de solução. |
| **Limpeza de Cache** | Varre e remove com segurança fragmentos `.tmp` e `.part` de downloads interrompidos. |

---

## 🧩 Guia de Instalação da Extensão no Navegador

### Passo 1: Abrir a página de extensões
- **Microsoft Edge**: Digite `edge://extensions` na barra de endereços e pressione Enter.
- **Google Chrome**: Digite `chrome://extensions` na barra de endereços e pressione Enter.

### Passo 2: Ativar o «Modo de desenvolvedor»
- No canto superior direito, ative o botão **Modo de desenvolvedor** (Developer mode).
- O botão **[Carregar sem compactação]** será exibido.

### Passo 3: Selecionar a pasta da extensão
1. Clique em **[Carregar sem compactação]**.
2. Selecione a pasta **`m3u8-sniffer-extension`**.
3. Confirme a seleção. A extensão está instalada!
4. Fixe o **StarStream Media Sniffer** na barra de ferramentas.

---

## ⚖️ Isenção de Responsabilidade

1. **Pesquisa Técnica e Uso Pessoal**: Este projeto destina-se ao estudo de protocolos de streaming e backups pessoais legítimos.
2. **Propriedade Intelectual**: Respeite os direitos autorais. O uso comercial não autorizado ou pirataria é expressamente proibido.
3. **Limitação de Responsabilidade**: Esta ferramenta não hospeda nem distribui conteúdo multimídia.

---

## 📄 Licença

Distribuído sob a [Licença MIT](LICENSE). Agradecimentos especiais a [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) e [FFmpeg](https://ffmpeg.org/).
---

## 📬 Contato com o Autor e Suporte Técnico

Se você encontrar algum problema, bug ou tiver dúvidas durante o uso, ou se tiver sugestões de melhorias e pedidos de novos recursos, sinta-se à vontade para entrar em contato com o autor por e-mail:

- **QQ Mail**: [2792893068@qq.com](mailto:2792893068@qq.com)
- **Gmail**: [lepa23216@gmail.com](mailto:lepa23216@gmail.com)

Responderemos e atenderemos às suas dúvidas e sugestões o mais rápido possível! Obrigado pelo seu apoio e feedback!
