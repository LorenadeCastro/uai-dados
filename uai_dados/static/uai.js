/* =========================================================================
   UAI Dados — runtime do navegador
   -------------------------------------------------------------------------
   Faz parte da FERRAMENTA, não das páginas. Quem monta painel escreve só
   Python; este arquivo é escrito uma vez e ninguém da equipe precisa tocar.

   O que ele faz, em ordem:
     1. lê o JSON embutido na página (formato colunar) e remonta os registros;
     2. monta os filtros a partir das bases;
     3. a cada mudança de filtro, recalcula tudo numa única passada por base.

   Sobre desempenho: a matriz NÃO recalcula célula por célula. Cada base é
   percorrida uma vez por mudança de filtro e, para cada linha que passa, o
   valor é somado em todos os níveis da hierarquia de uma vez. O custo é
   O(linhas x níveis), não O(linhas x células).
   ========================================================================= */
(function () {
  "use strict";

  const SEP = "\u0001"; // separador interno do caminho hierárquico
  const pagina = JSON.parse(document.getElementById("uai-dados-pagina").textContent);

  const CORES = ["#223a5e", "#b3232e", "#6b7f9e", "#c98a3d", "#4d7d6a",
                 "#8a5a83", "#3d6f8e", "#a06c4f"];

  /* ---------- Formatação ------------------------------------------------ */
  // Duas casas decimais em toda parte: valor orçamentário tem centavos, e
  // arredondar na tela faz a soma exibida divergir da soma real.
  const fmtMoeda = new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "BRL",
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
  const fmtNumero = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
  const fmtInteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const fmtPct = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });

  function formatar(valor, formato) {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return "–";
    if (typeof valor !== "number") return String(valor);
    if (formato === "moeda") return fmtMoeda.format(valor);
    if (formato === "inteiro") return fmtInteiro.format(valor);
    if (formato === "percentual") return fmtPct.format(valor);
    return fmtNumero.format(valor);
  }

  function numero(v) {
    if (typeof v === "number") return Number.isFinite(v) ? v : 0;
    if (v == null || v === "") return 0;
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  /* ---------- Bases ------------------------------------------------------
     Uma coluna chega em um de dois formatos: lista simples, ou
     {d: [valores distintos], i: [índices]} — o dicionário que o build usa
     para não repetir o mesmo texto em dezenas de milhares de linhas.
     Aqui os dois viram a mesma coisa: um array de valores por linha. */
  function decodificar(coluna) {
    if (Array.isArray(coluna)) return coluna;
    const { d, i } = coluna;
    const saida = new Array(i.length);
    for (let k = 0; k < i.length; k++) saida[k] = i[k] === null ? null : d[i[k]];
    return saida;
  }

  const bases = {};
  for (const [nome, base] of Object.entries(pagina.bases)) {
    const colunas = base.colunas;
    const valores = colunas.map((c) => decodificar(base.dados[c]));
    const total = colunas.length ? valores[0].length : 0;
    const lista = new Array(total);
    for (let i = 0; i < total; i++) {
      const linha = {};
      for (let c = 0; c < colunas.length; c++) linha[colunas[c]] = valores[c][i];
      lista[i] = linha;
    }
    bases[nome] = { registros: lista, colunas: new Set(colunas) };
  }
  const principal = bases[pagina.base_principal].registros;

  const selecoes = {}; // coluna -> valor selecionado ("" = todos)

  function passaFiltros(linha, colunasDaBase) {
    for (const [coluna, valor] of Object.entries(selecoes)) {
      if (valor === "") continue;
      // Coluna ausente na base: a linha passa. O build avisa quais bases
      // ficam de fora e a tela repete isso no rótulo do filtro.
      if (!colunasDaBase.has(coluna)) continue;
      if (String(linha[coluna]) !== valor) return false;
    }
    return true;
  }

  function filtrar(nome) {
    const { registros, colunas } = bases[nome];
    return registros.filter((linha) => passaFiltros(linha, colunas));
  }

  /* ---------- Filtros ---------------------------------------------------- */
  function montarFiltros() {
    const secao = document.getElementById("uai-filtros");
    if (!pagina.filtros.length) { secao.style.display = "none"; return; }
    const nomesBases = Object.keys(bases);

    for (const filtro of pagina.filtros) {
      const valores = new Set();
      for (const nome of nomesBases) {
        if (!bases[nome].colunas.has(filtro.coluna)) continue;
        for (const linha of bases[nome].registros) {
          const v = linha[filtro.coluna];
          if (v !== null && v !== undefined && v !== "") valores.add(String(v));
        }
      }
      const ordenados = [...valores].sort((a, b) =>
        a.localeCompare(b, "pt-BR", { numeric: true }));

      const bloco = document.createElement("div");
      bloco.className = "uai-filtro";

      const rotulo = document.createElement("label");
      rotulo.htmlFor = filtro.id;
      rotulo.textContent = filtro.rotulo;

      const seletor = document.createElement("select");
      seletor.id = filtro.id;
      seletor.append(new Option("Todos", ""));
      for (const v of ordenados) seletor.append(new Option(v, v));
      seletor.addEventListener("change", () => {
        selecoes[filtro.coluna] = seletor.value;
        atualizarTudo();
      });

      bloco.append(rotulo, seletor);

      const aplicaveis = pagina.filtros_por_base[filtro.coluna] || nomesBases;
      const ausentes = nomesBases.filter((n) => !aplicaveis.includes(n));
      if (ausentes.length) {
        const aviso = document.createElement("span");
        aviso.className = "uai-filtro-aviso";
        aviso.textContent = `não se aplica a: ${ausentes.join(", ")}`;
        bloco.append(aviso);
      }

      secao.append(bloco);
      selecoes[filtro.coluna] = "";
    }

    const limpar = document.createElement("button");
    limpar.className = "uai-limpar";
    limpar.textContent = "Limpar filtros";
    limpar.addEventListener("click", () => {
      for (const filtro of pagina.filtros) {
        selecoes[filtro.coluna] = "";
        document.getElementById(filtro.id).value = "";
      }
      atualizarTudo();
    });
    secao.append(limpar);
  }

  /* ---------- Avaliador de fórmulas --------------------------------------
     Resolve "C - A", "(D / B)" e afins. Nada de eval: um analisador de
     expressão pequeno, que só aceita letras, números, + - * / e parênteses. */
  function avaliarFormula(expressao, valoresPorLetra) {
    const tokens = expressao.match(/[A-Z]|\d+\.?\d*|[()+\-*/]/g) || [];
    let pos = 0;
    const olhar = () => tokens[pos];
    const consumir = () => tokens[pos++];

    function fator() {
      const t = consumir();
      if (t === "(") { const v = expr(); consumir(); return v; }
      if (t === "-") return -fator();
      if (/^[A-Z]$/.test(t)) return valoresPorLetra[t] ?? 0;
      return Number(t);
    }
    function termo() {
      let v = fator();
      while (olhar() === "*" || olhar() === "/") {
        const op = consumir();
        const d = fator();
        v = op === "*" ? v * d : (d === 0 ? 0 : v / d);
      }
      return v;
    }
    function expr() {
      let v = termo();
      while (olhar() === "+" || olhar() === "-") {
        const op = consumir();
        v = op === "+" ? v + termo() : v - termo();
      }
      return v;
    }
    return expr();
  }

  /* ---------- Matriz hierárquica ----------------------------------------- */
  function criarMatriz(comp) {
    const cartao = document.createElement("div");
    cartao.className = "uai-cartao";
    cartao.innerHTML =
      `<div class="uai-matriz-topo"><h3>${comp.titulo}</h3>` +
      `<button class="uai-exportar" type="button">Baixar XLSX</button></div>` +
      `<div class="uai-tabela-envolucro"><table class="uai-matriz" id="${comp.id}"></table></div>`;
    document.getElementById("uai-componentes").append(cartao);
    cartao.querySelector(".uai-exportar").addEventListener("click", () => exportarXlsx(comp));
  }

  /**
   * Percorre cada base UMA vez e acumula os valores em todos os níveis.
   * Devolve { valores: Map(caminho -> Float64Array), filhos: Map(caminho -> Set) }.
   */
  function calcularMatriz(comp) {
    const niveis = comp.hierarquia.length;
    const nCols = comp.colunas.length;
    const valores = new Map();
    const filhos = new Map();

    valores.set("", new Float64Array(nCols));
    filhos.set("", new Set());

    const porBase = new Map();
    comp.colunas.forEach((coluna, indice) => {
      if (!coluna.base) return;
      if (!porBase.has(coluna.base)) porBase.set(coluna.base, []);
      porBase.get(coluna.base).push({ ...coluna, indice });
    });

    const caminhos = new Array(niveis);

    for (const [nomeBase, colunasDaBase] of porBase) {
      for (const linha of filtrar(nomeBase)) {
        let caminho = "";
        for (let n = 0; n < niveis; n++) {
          const bruto = linha[comp.hierarquia[n]];
          const rotulo = bruto === null || bruto === undefined || bruto === ""
            ? comp.rotulo_nulo : String(bruto);
          caminho = n === 0 ? rotulo : caminho + SEP + rotulo;
          caminhos[n] = caminho;
        }

        for (const coluna of colunasDaBase) {
          if (coluna.ano !== null && String(linha.ano) !== coluna.ano) continue;
          const v = numero(linha[coluna.valor]);
          if (v === 0) continue;

          valores.get("")[coluna.indice] += v;
          for (let n = 0; n < niveis; n++) {
            let acumulado = valores.get(caminhos[n]);
            if (!acumulado) {
              acumulado = new Float64Array(nCols);
              valores.set(caminhos[n], acumulado);
              filhos.set(caminhos[n], new Set());
              filhos.get(n === 0 ? "" : caminhos[n - 1]).add(caminhos[n]);
            }
            acumulado[coluna.indice] += v;
          }
        }
      }
    }

    // Colunas calculadas, depois de todas as somas.
    const porLetra = {};
    comp.colunas.forEach((coluna, indice) => {
      if (coluna.letra) porLetra[coluna.letra] = indice;
    });
    const calculadas = comp.colunas
      .map((coluna, indice) => ({ coluna, indice }))
      .filter((x) => x.coluna.formula);
    if (calculadas.length) {
      for (const acumulado of valores.values()) {
        const contexto = {};
        for (const [letra, i] of Object.entries(porLetra)) contexto[letra] = acumulado[i];
        for (const { coluna, indice } of calculadas) {
          acumulado[indice] = avaliarFormula(coluna.formula, contexto);
        }
      }
    }

    return { valores, filhos };
  }

  const estadoMatriz = new Map(); // id -> Set de caminhos expandidos

  function atualizarMatriz(comp) {
    const { valores, filhos } = calcularMatriz(comp);
    const tabela = document.getElementById(comp.id);

    if (!estadoMatriz.has(comp.id)) {
      const expandir = new Set();
      const abrir = (caminho, nivel) => {
        if (nivel >= comp.niveis_visiveis) return;
        expandir.add(caminho);
        for (const filho of filhos.get(caminho) || []) abrir(filho, nivel + 1);
      };
      abrir("", 0);
      estadoMatriz.set(comp.id, expandir);
    }
    const expandidos = estadoMatriz.get(comp.id);

    const cabecalho =
      `<thead><tr><th class="uai-matriz-desc">DESCRIÇÃO</th>` +
      comp.colunas.map((c) => `<th class="numero">${c.titulo}</th>`).join("") +
      `</tr></thead>`;

    const celulas = (acumulado) => comp.colunas.map((coluna, i) => {
      const v = acumulado[i];
      return `<td class="numero${v < 0 ? " neg" : ""}">${formatar(v, coluna.formato)}</td>`;
    }).join("");

    const linhasHtml = [
      `<tr class="uai-nivel-total"><td>${comp.total}</td>${celulas(valores.get(""))}</tr>`,
    ];

    const ordenar = (a, b) => {
      const ra = a.split(SEP).pop(), rb = b.split(SEP).pop();
      if (ra === comp.rotulo_nulo) return 1;
      if (rb === comp.rotulo_nulo) return -1;
      return ra.localeCompare(rb, "pt-BR", { numeric: true });
    };

    const desenhar = (caminho, nivel) => {
      for (const filho of [...(filhos.get(caminho) || [])].sort(ordenar)) {
        const acumulado = valores.get(filho);
        if (comp.ocultar_zerados && acumulado.every((v) => v === 0)) continue;
        const temFilhos = (filhos.get(filho) || new Set()).size > 0;
        const aberto = expandidos.has(filho);
        const rotulo = filho.split(SEP).pop();
        linhasHtml.push(
          `<tr class="uai-nivel-${Math.min(nivel, 5)}${temFilhos ? " uai-expansivel" : ""}"` +
          ` data-caminho="${encodeURIComponent(filho)}">` +
          `<td style="padding-left:${0.6 + nivel * 1.3}rem" title="${rotulo}">` +
          `<span class="uai-marca">${temFilhos ? (aberto ? "−" : "+") : ""}</span>${rotulo}</td>` +
          celulas(acumulado) + `</tr>`
        );
        if (aberto) desenhar(filho, nivel + 1);
      }
    };
    desenhar("", 0);

    tabela.innerHTML = cabecalho + `<tbody>${linhasHtml.join("")}</tbody>`;
    tabela.querySelectorAll("tr.uai-expansivel").forEach((tr) => {
      tr.addEventListener("click", () => {
        const caminho = decodeURIComponent(tr.dataset.caminho);
        if (expandidos.has(caminho)) expandidos.delete(caminho);
        else expandidos.add(caminho);
        atualizarMatriz(comp);
      });
    });
  }

  /* ---------- Exportação XLSX --------------------------------------------
     Sem biblioteca externa: um .xlsx é um zip de XML. O zip vai sem
     compressão (método "stored"), o que cabe em poucas linhas.

     A planilha sai formatada de verdade: valores como NÚMERO com duas
     casas (nada de notação científica), largura de coluna calculada pelo
     conteúdo, cabeçalho fixo ao rolar e a hierarquia recuada por nível,
     usando o recuo real do Excel em vez de espaços no texto. */

  function exportarXlsx(comp) {
    const { valores, filhos } = calcularMatriz(comp);

    const linhas = [
      { tipo: "cabecalho", celulas: ["DESCRIÇÃO", ...comp.colunas.map((c) => c.titulo)] },
      { tipo: "total", nivel: 0, celulas: [comp.total, ...Array.from(valores.get(""))] },
    ];

    const ordenar = (a, b) => {
      const ra = a.split(SEP).pop(), rb = b.split(SEP).pop();
      if (ra === comp.rotulo_nulo) return 1;
      if (rb === comp.rotulo_nulo) return -1;
      return ra.localeCompare(rb, "pt-BR", { numeric: true });
    };
    const percorrer = (caminho, nivel) => {
      for (const filho of [...(filhos.get(caminho) || [])].sort(ordenar)) {
        const acumulado = valores.get(filho);
        if (comp.ocultar_zerados && acumulado.every((v) => v === 0)) continue;
        linhas.push({
          tipo: "dado",
          nivel: nivel + 1,
          celulas: [filho.split(SEP).pop(), ...Array.from(acumulado)],
        });
        percorrer(filho, nivel + 1);
      }
    };
    percorrer("", 0);

    const aplicados = [
      { tipo: "cabecalho", celulas: ["Filtro", "Seleção"] },
      ...pagina.filtros.map((f) => ({
        tipo: "dado", nivel: 0,
        celulas: [f.rotulo, selecoes[f.coluna] || "(todos)"],
      })),
      { tipo: "dado", nivel: 0, celulas: ["Gerado em", new Date().toLocaleString("pt-BR")] },
    ];

    const arquivo = comp.titulo.toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

    baixarXlsx(`${arquivo}.xlsx`, [
      { nome: comp.titulo.slice(0, 28), linhas, congelar: true },
      { nome: "Filtros aplicados", linhas: aplicados },
    ]);
  }

  function escaparXml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function letraColuna(indice) {
    let s = "";
    let n = indice + 1;
    while (n > 0) {
      const resto = (n - 1) % 26;
      s = String.fromCharCode(65 + resto) + s;
      n = Math.floor((n - resto) / 26);
    }
    return s;
  }

  /* Índices de estilo, na mesma ordem em que aparecem em cellXfs (estilosXml).
     Manter os dois lados em sincronia. */
  const EST = {
    padrao: 0,
    cabecalhoTexto: 1,
    cabecalhoNumero: 2,
    rotuloTotal: 3,
    rotulo: 4,      // 4..9 = recuo 0..5
    moeda: 10,
    moedaTotal: 11,
  };

  function estilosXml() {
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">` +
      // 164: duas casas, milhar, negativo em vermelho entre parênteses
      `<numFmts count="1">` +
      `<numFmt numFmtId="164" formatCode="#,##0.00_);[Red]\\(#,##0.00\\)"/>` +
      `</numFmts>` +
      `<fonts count="3">` +
      `<font><sz val="11"/><name val="Calibri"/></font>` +
      `<font><sz val="11"/><name val="Calibri"/><b/></font>` +
      `<font><sz val="11"/><name val="Calibri"/><b/><color rgb="FFFFFFFF"/></font>` +
      `</fonts>` +
      `<fills count="3">` +
      `<fill><patternFill patternType="none"/></fill>` +
      `<fill><patternFill patternType="gray125"/></fill>` +
      `<fill><patternFill patternType="solid"><fgColor rgb="FF17273F"/>` +
      `<bgColor indexed="64"/></patternFill></fill>` +
      `</fills>` +
      `<borders count="2">` +
      `<border><left/><right/><top/><bottom/><diagonal/></border>` +
      `<border><left/><right/><top/><bottom style="medium">` +
      `<color rgb="FF17273F"/></bottom><diagonal/></border>` +
      `</borders>` +
      `<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>` +
      `<cellXfs count="12">` +
      // 0 padrão
      `<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>` +
      // 1 cabeçalho de texto
      `<xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1">` +
      `<alignment horizontal="left" vertical="center"/></xf>` +
      // 2 cabeçalho de número
      `<xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1">` +
      `<alignment horizontal="right" vertical="center" wrapText="1"/></xf>` +
      // 3 rótulo do TOTAL
      `<xf numFmtId="0" fontId="1" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"/>` +
      // 4..9 rótulos com recuo 0..5
      [0, 1, 2, 3, 4, 5].map((i) =>
        `<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">` +
        `<alignment indent="${i}"/></xf>`).join("") +
      // 10 moeda
      `<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>` +
      // 11 moeda do TOTAL
      `<xf numFmtId="164" fontId="1" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>` +
      `</cellXfs>` +
      `<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>` +
      `</styleSheet>`;
  }

  function estiloDaCelula(linha, coluna) {
    if (linha.tipo === "cabecalho") return coluna === 0 ? EST.cabecalhoTexto : EST.cabecalhoNumero;
    if (linha.tipo === "total") return coluna === 0 ? EST.rotuloTotal : EST.moedaTotal;
    if (coluna === 0) return EST.rotulo + Math.min(linha.nivel ?? 0, 5);
    return EST.moeda;
  }

  /* Largura de coluna pelo conteúdo mais longo, com teto — a primeira
     coluna é a que mais sofria: no Excel padrão ela cortava a descrição. */
  function largurasDe(linhas) {
    const larguras = [];
    for (const linha of linhas) {
      linha.celulas.forEach((valor, c) => {
        const texto = typeof valor === "number"
          ? fmtNumero.format(valor)
          : String(valor ?? "");
        const recuo = c === 0 ? (linha.nivel ?? 0) * 2 : 0;
        larguras[c] = Math.max(larguras[c] ?? 10, texto.length + recuo + 3);
      });
    }
    return larguras.map((l, c) => Math.min(l, c === 0 ? 58 : 22));
  }

  function folhaXml(aba) {
    const { linhas, congelar } = aba;
    const cols = largurasDe(linhas)
      .map((largura, c) => `<col min="${c + 1}" max="${c + 1}" width="${largura}" customWidth="1"/>`)
      .join("");

    const painel = congelar
      ? `<sheetViews><sheetView workbookViewId="0" tabSelected="1">` +
        `<pane xSplit="1" ySplit="1" topLeftCell="B2" activePane="bottomRight" state="frozen"/>` +
        `</sheetView></sheetViews>`
      : `<sheetViews><sheetView workbookViewId="0"/></sheetViews>`;

    const corpo = linhas.map((linha, r) => {
      const celulas = linha.celulas.map((valor, c) => {
        const ref = `${letraColuna(c)}${r + 1}`;
        const estilo = estiloDaCelula(linha, c);
        if (typeof valor === "number") {
          return `<c r="${ref}" s="${estilo}"><v>${Number.isFinite(valor) ? valor : 0}</v></c>`;
        }
        return `<c r="${ref}" s="${estilo}" t="inlineStr"><is>` +
          `<t xml:space="preserve">${escaparXml(valor)}</t></is></c>`;
      }).join("");
      const altura = linha.tipo === "cabecalho" ? ` ht="30" customHeight="1"` : "";
      return `<row r="${r + 1}"${altura}>${celulas}</row>`;
    }).join("");

    const ultima = `${letraColuna(Math.max(...linhas.map((l) => l.celulas.length)) - 1)}${linhas.length}`;
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">` +
      `<dimension ref="A1:${ultima}"/>` + painel +
      `<cols>${cols}</cols><sheetData>${corpo}</sheetData>` +
      `<autoFilter ref="A1:${ultima}"/>` +
      `</worksheet>`;
  }

  function baixarXlsx(nomeArquivo, abas) {
    const arquivos = [];
    const codificar = new TextEncoder();
    const add = (nome, texto) => arquivos.push({ nome, dados: codificar.encode(texto) });

    add("[Content_Types].xml",
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">` +
      `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>` +
      `<Default Extension="xml" ContentType="application/xml"/>` +
      `<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>` +
      `<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>` +
      abas.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("") +
      `</Types>`);

    add("_rels/.rels",
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
      `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>` +
      `</Relationships>`);

    add("xl/workbook.xml",
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ` +
      `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>` +
      abas.map((aba, i) => `<sheet name="${escaparXml(aba.nome)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("") +
      `</sheets></workbook>`);

    const rIdEstilos = abas.length + 1;
    add("xl/_rels/workbook.xml.rels",
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
      `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">` +
      abas.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("") +
      `<Relationship Id="rId${rIdEstilos}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
      `</Relationships>`);

    add("xl/styles.xml", estilosXml());
    abas.forEach((aba, i) => add(`xl/worksheets/sheet${i + 1}.xml`, folhaXml(aba)));

    const blob = new Blob([montarZip(arquivos)], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = nomeArquivo;
    link.click();
    URL.revokeObjectURL(url);
  }

  const TABELA_CRC = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = TABELA_CRC[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  function montarZip(arquivos) {
    const pedacos = [];
    const central = [];
    let deslocamento = 0;
    const u16 = (v) => [v & 0xff, (v >> 8) & 0xff];
    const u32 = (v) => [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >>> 24) & 0xff];

    for (const arquivo of arquivos) {
      const nome = new TextEncoder().encode(arquivo.nome);
      const crc = crc32(arquivo.dados);
      const cabecalho = [
        ...u32(0x04034b50), ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
        ...u32(crc), ...u32(arquivo.dados.length), ...u32(arquivo.dados.length),
        ...u16(nome.length), ...u16(0),
      ];
      pedacos.push(new Uint8Array(cabecalho), nome, arquivo.dados);
      central.push({ nome, crc, tamanho: arquivo.dados.length, deslocamento });
      deslocamento += cabecalho.length + nome.length + arquivo.dados.length;
    }

    const inicioCentral = deslocamento;
    let tamanhoCentral = 0;
    for (const item of central) {
      const registro = [
        ...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
        ...u32(item.crc), ...u32(item.tamanho), ...u32(item.tamanho),
        ...u16(item.nome.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
        ...u32(0), ...u32(item.deslocamento),
      ];
      pedacos.push(new Uint8Array(registro), item.nome);
      tamanhoCentral += registro.length + item.nome.length;
    }

    pedacos.push(new Uint8Array([
      ...u32(0x06054b50), ...u16(0), ...u16(0),
      ...u16(central.length), ...u16(central.length),
      ...u32(tamanhoCentral), ...u32(inicioCentral), ...u16(0),
    ]));

    const total = pedacos.reduce((s, p) => s + p.length, 0);
    const saida = new Uint8Array(total);
    let pos = 0;
    for (const pedaco of pedacos) { saida.set(pedaco, pos); pos += pedaco.length; }
    return saida;
  }

  /* ---------- Componentes simples ---------------------------------------- */
  function agregar(linhas, coluna, modo) {
    if (modo === "contagem") return linhas.length;
    if (modo === "distintos") return new Set(linhas.map((l) => l[coluna])).size;
    const nums = linhas.map((l) => Number(l[coluna])).filter((n) => !Number.isNaN(n));
    if (!nums.length) return null;
    const soma = nums.reduce((a, b) => a + b, 0);
    return modo === "media" ? soma / nums.length : soma;
  }

  function agruparPor(linhas, chave) {
    const grupos = new Map();
    for (const linha of linhas) {
      const v = String(linha[chave]);
      if (!grupos.has(v)) grupos.set(v, []);
      grupos.get(v).push(linha);
    }
    return grupos;
  }

  function criarEstruturas() {
    const secaoKpi = document.getElementById("uai-indicadores");
    const secaoComp = document.getElementById("uai-componentes");
    for (const comp of pagina.componentes) {
      if (comp.tipo === "indicador") {
        const cartao = document.createElement("div");
        cartao.className = "uai-indicador";
        cartao.innerHTML = `<div class="rotulo">${comp.rotulo}</div><div class="valor" id="${comp.id}"></div>`;
        secaoKpi.append(cartao);
      } else if (comp.tipo === "matriz") {
        criarMatriz(comp);
      } else {
        const cartao = document.createElement("div");
        cartao.className = "uai-cartao";
        cartao.innerHTML = comp.tipo === "grafico"
          ? `<h3>${comp.titulo}</h3><div id="${comp.id}"></div>`
          : `<div class="uai-tabela-envolucro" id="${comp.id}"></div><p class="uai-tabela-aviso" id="${comp.id}-aviso"></p>`;
        secaoComp.append(cartao);
      }
    }
    if (!secaoKpi.children.length) secaoKpi.style.display = "none";
  }

  function atualizarGrafico(comp, linhas) {
    const layout = {
      margin: { l: 70, r: 20, t: 10, b: 60 },
      font: { family: "Segoe UI, system-ui, sans-serif", size: 14, color: "#1c2430" },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      separators: ",.", height: 420,
    };
    let traces = [];
    if (comp.tipo_grafico === "pizza") {
      const grupos = agruparPor(linhas, comp.x);
      const rotulos = [...grupos.keys()];
      traces = [{ type: "pie", labels: rotulos,
        values: rotulos.map((r) => agregar(grupos.get(r), comp.y, comp.agregacao)),
        marker: { colors: CORES }, textinfo: "label+percent" }];
    } else if (comp.cor) {
      const series = agruparPor(linhas, comp.cor);
      const categorias = [...agruparPor(linhas, comp.x).keys()];
      let i = 0;
      for (const [nome, ls] of series) {
        const porCat = agruparPor(ls, comp.x);
        traces.push({
          type: comp.tipo_grafico === "linhas" ? "scatter" : "bar",
          mode: comp.tipo_grafico === "linhas" ? "lines+markers" : undefined,
          name: nome, x: categorias,
          y: categorias.map((c) => porCat.has(c) ? agregar(porCat.get(c), comp.y, comp.agregacao) : null),
          marker: { color: CORES[i++ % CORES.length] },
        });
      }
      layout.barmode = "group";
      layout.legend = { orientation: "h", y: -0.2 };
    } else {
      const grupos = agruparPor(linhas, comp.x);
      const pares = [...grupos.entries()].map(([c, ls]) => [c, agregar(ls, comp.y, comp.agregacao)]);
      if (comp.ordenar === "y") pares.sort((a, b) => b[1] - a[1]);
      traces = [{
        type: comp.tipo_grafico === "linhas" ? "scatter" : "bar",
        mode: comp.tipo_grafico === "linhas" ? "lines+markers" : undefined,
        x: pares.map((p) => p[0]), y: pares.map((p) => p[1]),
        marker: { color: "#223a5e" },
      }];
    }
    if (comp.tipo_grafico !== "pizza" && comp.formato === "moeda") {
      layout.yaxis = { tickprefix: "R$ ", tickformat: ",.0f" };
    }
    Plotly.react(comp.id, traces, layout,
      { displaylogo: false, responsive: true, locale: "pt-BR" });
  }

  function atualizarTabela(comp, linhas) {
    const colunas = Object.keys(comp.colunas).length
      ? comp.colunas
      : Object.fromEntries(Object.keys(principal[0] || {}).map((c) => [c, c]));
    const visiveis = linhas.slice(0, comp.limite);
    const cabecalho = Object.entries(colunas).map(([col, rot]) =>
      `<th${comp.formatos[col] ? ' class="numero"' : ""}>${rot}</th>`).join("");
    const corpo = visiveis.map((linha) => "<tr>" + Object.keys(colunas).map((col) => {
      const f = comp.formatos[col];
      return `<td${f ? ' class="numero"' : ""}>${formatar(f ? Number(linha[col]) : linha[col], f)}</td>`;
    }).join("") + "</tr>").join("");
    document.getElementById(comp.id).innerHTML =
      `<table class="uai-tabela"><thead><tr>${cabecalho}</tr></thead><tbody>${corpo}</tbody></table>`;
    document.getElementById(comp.id + "-aviso").textContent = linhas.length > comp.limite
      ? `Exibindo ${comp.limite.toLocaleString("pt-BR")} de ${linhas.length.toLocaleString("pt-BR")} registros.`
      : `${linhas.length.toLocaleString("pt-BR")} registros.`;
  }

  function atualizarTudo() {
    let linhasPrincipal = null;
    for (const comp of pagina.componentes) {
      if (comp.tipo === "matriz") { atualizarMatriz(comp); continue; }
      if (linhasPrincipal === null) linhasPrincipal = filtrar(pagina.base_principal);
      if (comp.tipo === "indicador") {
        document.getElementById(comp.id).textContent =
          formatar(agregar(linhasPrincipal, comp.coluna, comp.agregacao), comp.formato);
      } else if (comp.tipo === "grafico") {
        atualizarGrafico(comp, linhasPrincipal);
      } else if (comp.tipo === "tabela") {
        atualizarTabela(comp, linhasPrincipal);
      }
    }
  }

  montarFiltros();
  criarEstruturas();
  atualizarTudo();
})();
