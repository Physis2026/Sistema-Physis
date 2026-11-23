/* Physis · lógica de Soluções baseadas na Natureza (SbN)
   Escolhe plantas e monta consórcios a partir de sistema/physis-plantas.json:
   filtros por bioma, solo, clima e altitude; consórcios de agrofloresta (estratos e sucessão), horta, pomar,
   restauração de APP (preenchimento × diversidade) e jardim de chuva; mudas pela área e pelo espaçamento;
   leitura das áreas desenhadas no Planejador (localStorage "physis.terreno.v1"); correção das combinações A/B/C.
   Funções puras (sem DOM e sem internet). Os desenhos de tela usam esc/n2 da plataforma quando existirem.
   Uso: SBN_LOGICA.carregar(baseJson) uma vez; depois filtrar(), montarConsorcio(), mudas(), lerTerreno()… */
(function (raiz) {
  "use strict";
  const VERSAO = "2026-11-15";
  const BIOMAS = ["Mata Atlântica", "Cerrado", "Caatinga", "Amazônia", "Pampa", "Pantanal"];
  const ESTRATOS_SAF = ["emergente", "alto", "medio", "baixo", "rasteiro"];
  const NOME_ESTRATO = { emergente: "Emergente", alto: "Alto", medio: "Médio", baixo: "Baixo", rasteiro: "Rasteiro", trepadeira: "Trepadeira", aquatica: "Aquática" };
  const CICLOS = ["placenta1", "placenta2", "secundaria", "climax"];
  const NOME_CICLO = { placenta1: "Placenta I", placenta2: "Placenta II", secundaria: "Secundária", climax: "Clímax" };
  /* cobertura de copa por estrato, em % da área (agrofloresta sucessional: Götsch; Embrapa SAF).
     Cada estrato é uma camada própria, por isso a soma passa de 100%. */
  const COBERTURA = {
    emergente: { alvo: 20, min: 10, max: 30 }, alto: { alvo: 40, min: 25, max: 50 }, medio: { alvo: 50, min: 35, max: 65 },
    baixo: { alvo: 60, min: 40, max: 80 }, rasteiro: { alvo: 70, min: 40, max: 100 }
  };
  const OBJETIVOS = {
    agrofloresta: { nome: "Agrofloresta", fun: ["alimento", "nitrogenio", "biomassa", "solo", "polinizadores", "sombra"] },
    horta: { nome: "Horta", fun: ["alimento", "protecao", "medicinal", "polinizadores"] },
    pomar: { nome: "Pomar", fun: ["alimento", "polinizadores", "nitrogenio", "animais"] },
    restauracao_app: { nome: "Restauração de APP", fun: ["agua", "barranco", "solo", "animais", "polinizadores", "nitrogenio"] },
    jardim_chuva: { nome: "Jardim de chuva", fun: ["agua", "polinizadores", "ornamental"] }
  };
  const ALVO_NATIVAS = { agrofloresta: 50, horta: 20, pomar: 40, restauracao_app: 100, jardim_chuva: 60 };   /* padrão quando nativas_pct não vem */
  const GRADE_RESTAURACAO = [3, 2];          /* 3 m entre linhas × 2 m entre plantas: 1.667 mudas/ha */
  const NATIVAS_MIN_APP = 50;                /* Lei 12.651/2012, art. 61-A, § 13, IV (pequena propriedade) */
  const AREA_UTIL_HORTA = 0.65;              /* canteiros de 1,0–1,2 m com caminhos de 0,4–0,5 m */

  let BASE = null;

  /* ───────────── utilidades ───────────── */
  const semAcento = s => String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
  const num = v => { if (typeof v === "number") return v; const x = parseFloat(String(v == null ? "" : v).replace(",", ".")); return isFinite(x) ? x : null; };
  const lista = x => Array.isArray(x) ? x : (x == null || x === "" ? [] : [x]);
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  function plantasDe(x) { if (!x) return BASE ? (Array.isArray(BASE) ? BASE : BASE.plantas || []) : []; return Array.isArray(x) ? x : (x.plantas || []); }
  function normTextura(t) { const s = semAcento(t); if (!s) return ""; if (/argil/.test(s)) return "argiloso"; if (/aren/.test(s)) return "arenoso"; if (/medi|franc|silt/.test(s)) return "médio"; return ""; }
  function eEspecie(p) { return !!p && p.item_viveiro !== true && p.item_grupo !== true && p.especie !== false && !/muda \(viveiro\)/i.test(p.tipo || ""); }
  const REGIOES = { Norte: ["AC", "AM", "AP", "PA", "RO", "RR", "TO"], Nordeste: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["DF", "GO", "MS", "MT"], Sudeste: ["ES", "MG", "RJ", "SP"], Sul: ["PR", "RS", "SC"] };
  const regiaoDaUf = uf => Object.keys(REGIOES).find(r => REGIOES[r].includes(String(uf || "").toUpperCase())) || "";
  const POR_UF_PADRAO = { AC: ["Amazônia"], AM: ["Amazônia"], AP: ["Amazônia"], PA: ["Amazônia"], RR: ["Amazônia"], RO: ["Amazônia", "Cerrado"], MT: ["Amazônia", "Cerrado", "Pantanal"], MS: ["Cerrado", "Pantanal", "Mata Atlântica"], TO: ["Cerrado", "Amazônia"], MA: ["Cerrado", "Amazônia", "Caatinga"], PI: ["Caatinga", "Cerrado"], CE: ["Caatinga"], RN: ["Caatinga", "Mata Atlântica"], PB: ["Caatinga", "Mata Atlântica"], PE: ["Caatinga", "Mata Atlântica"], AL: ["Mata Atlântica", "Caatinga"], SE: ["Mata Atlântica", "Caatinga"], BA: ["Caatinga", "Cerrado", "Mata Atlântica"], GO: ["Cerrado"], DF: ["Cerrado"], MG: ["Cerrado", "Mata Atlântica", "Caatinga"], ES: ["Mata Atlântica"], RJ: ["Mata Atlântica"], SP: ["Mata Atlântica", "Cerrado"], PR: ["Mata Atlântica", "Cerrado"], SC: ["Mata Atlântica"], RS: ["Pampa", "Mata Atlântica"] };
  function porUf() { return (BASE && !Array.isArray(BASE) && BASE.biomas && BASE.biomas.por_uf) || POR_UF_PADRAO; }
  /* biomas de uma UF ou de uma região (para o filtro "região/UF" quando o bioma não foi escolhido) */
  function biomasDoLugar(c) {
    const pu = porUf();
    if (c.uf) return pu[String(c.uf).toUpperCase()] || null;
    if (c.regiao && REGIOES[c.regiao]) return [...new Set(REGIOES[c.regiao].flatMap(u => pu[u] || []))];
    return null;
  }
  const semBioma = b => !b || semAcento(b) === "todas" || semAcento(b) === "todos";
  function cultivavel(p, bioma) { const c = Array.isArray(p.cultivavel_em) && p.cultivavel_em.length ? p.cultivavel_em : (Array.isArray(p.biomas) ? p.biomas : []); return c.includes(bioma); }
  function nativaDe(p, bioma) { if (!bioma || /^tod[ao]s$/i.test(bioma)) return p.nativa_br === true; return Array.isArray(p.nativa_de) && p.nativa_de.includes(bioma); }
  function esp(p) { const e = p && p.espacamento; const a = e && num(e.entre_plantas_m), b = e && num(e.entre_linhas_m); return a > 0 && b > 0 ? [a, b] : null; }
  const areaPlanta = p => { const e = esp(p); return e ? e[0] * e[1] : null; };
  const genero = p => (String(p.cientifico || "").match(/^[A-Z][a-z]+/) || [""])[0];
  const temFun = (p, f) => f === "madeira" ? p.madeira === true : (Array.isArray(p.funcoes) && p.funcoes.includes(f));   /* madeira é campo próprio */
  const companheiras = (a, b) => (a.companheiras || []).includes(b.n) || (b.companheiras || []).includes(a.n);
  const antagonistas = (a, b) => (a.antagonistas || []).includes(b.n) || (b.antagonistas || []).includes(a.n);

  function carregar(base) { BASE = base || null; return api; }

  /* ───────────── filtros ───────────── */
  /* criterios: { bioma, somenteNativas, incluirInvasoras, incluirViveiro, altitude_m, irrigacao, luz,
       solo:{ textura, umido, seco, acido, acido_estrito }, clima:{ tmin_c, geada, chuva_mm_ano, meses_secos, temp_media_c },
       estrato, ciclo, funcoes:[], app, txt }
     Devolve a lista de motivos que excluem a planta (vazia = serve). */
  function avaliar(p, c) {
    c = c || {}; const m = [];
    if (!p) return ["planta inexistente"];
    if (!c.incluirViveiro && !eEspecie(p)) m.push("item de viveiro, não é espécie");
    if (!c.incluirInvasoras && p.invasora === true) m.push("invasora");
    /* bioma vazio ou "todas": sem filtro de bioma (as plantas sem bioma aparecem aqui) */
    const bl = semBioma(c.bioma) ? biomasDoLugar(c) : [c.bioma], onde = semBioma(c.bioma) ? (c.uf || c.regiao) : c.bioma;
    if (bl && bl.length) {
      if (!bl.some(b => cultivavel(p, b) || nativaDe(p, b))) m.push("fora do bioma " + (bl.length === 1 ? bl[0] : "de " + onde));
      if ((c.somenteNativas || c.zonaAmortecimento) && !bl.some(b => nativaDe(p, b))) m.push("não é nativa " + (bl.length === 1 ? "do bioma " + bl[0] : "dos biomas de " + onde));
    } else if ((c.somenteNativas || c.zonaAmortecimento) && p.nativa_br !== true) m.push("não é nativa do Brasil");
    if (c.zonaAmortecimento && (p.a_conferir || []).includes("invasora?")) m.push("possível invasora (a conferir): evitar perto de unidade de conservação");
    if (c.app && p.restauracao_app !== true) m.push("não indicada para APP");
    const alt = num(c.altitude_m);
    if (alt != null && Array.isArray(p.altitude_m) && p.altitude_m.length === 2) {
      const [a0, a1] = p.altitude_m; if (alt < a0 - 50 || alt > a1 + 50) m.push(`altitude ${Math.round(alt)} m fora da faixa ${a0}–${a1} m`);
    }
    const s = c.solo || {}, ps = p.solo || {};
    const tx = normTextura(s.textura);
    if (tx && Array.isArray(ps.textura) && ps.textura.length && !ps.textura.map(normTextura).includes(tx)) m.push("solo " + tx + " fora das texturas toleradas (" + ps.textura.join(", ") + ")");
    if (s.umido && !ps.umido) m.push("não tolera solo encharcado");
    if (s.seco && !ps.seco && !c.irrigacao) m.push("não tolera solo seco");
    if (s.acido && s.acido_estrito && !ps.acido) m.push("não tolera solo ácido");
    const k = c.clima || {}, pc = p.clima;
    if (pc) {
      const tmin = num(k.tmin_c);
      if (tmin != null && pc.tmin_tolerada_c != null && tmin < pc.tmin_tolerada_c) m.push(`frio de ${tmin} °C abaixo do tolerado (${pc.tmin_tolerada_c} °C)`);
      if (k.geada === true && pc.geada === "sensivel") m.push("sensível à geada");
      if (!c.irrigacao) {
        const ch = num(k.chuva_mm_ano);
        if (ch != null && Array.isArray(pc.chuva_mm_ano)) {
          if (ch < pc.chuva_mm_ano[0]) m.push(`chuva de ${Math.round(ch)} mm/ano abaixo do mínimo (${pc.chuva_mm_ano[0]} mm) sem irrigar`);
          else if (ch > pc.chuva_mm_ano[1]) m.push(`chuva de ${Math.round(ch)} mm/ano acima do máximo (${pc.chuva_mm_ano[1]} mm)`);
        }
        const ms = num(k.meses_secos);
        if (ms != null && pc.meses_secos_max != null && ms > pc.meses_secos_max) m.push(`${ms} meses secos; tolera ${pc.meses_secos_max} sem irrigar`);
      }
      const tm = num(k.temp_media_c);
      if (tm != null && Array.isArray(pc.temp_media_c) && (tm < pc.temp_media_c[0] - 1 || tm > pc.temp_media_c[1] + 1)) m.push(`temperatura média de ${tm} °C fora da faixa ${pc.temp_media_c[0]}–${pc.temp_media_c[1]} °C`);
    }
    if (c.luz && c.luz !== "sol" && !String(p.luz || "").includes(c.luz)) m.push("pede outra luz (" + (p.luz || "?") + ")");
    if (c.estrato && !lista(c.estrato).includes(p.estrato)) m.push("outro estrato");
    if (c.ciclo && !lista(c.ciclo).includes(p.ciclo)) m.push("outra fase da sucessão");
    if (Array.isArray(c.funcoes) && c.funcoes.length && !c.funcoes.every(f => temFun(p, f))) m.push("não cumpre todas as funções pedidas");
    if (c.madeira && p.madeira !== true) m.push("não é espécie de madeira");
    if (c.txt && !semAcento([p.nome, p.cientifico, p.tipo].join(" ")).includes(semAcento(c.txt))) m.push("não combina com a busca");
    return m;
  }
  function filtrar(plantas, criterios) { return plantasDe(plantas).filter(p => avaliar(p, criterios).length === 0); }

  /* ───────────── mudas ───────────── */
  function mudasInfo(planta, area_m2, densidade) {
    const A = num(area_m2) || 0, d = num(densidade), e = esp(planta);
    const linha = planta && planta.espacamento && /linha/.test(planta.espacamento.forma || "");
    if (d > 0) return { qtd: Math.ceil(A * d - 1e-9), densidade_m2: d, unidade: linha ? "plantas" : "mudas", espacamento: e, fonte: "densidade informada" };
    if (!e) return { qtd: 0, densidade_m2: null, unidade: "mudas", espacamento: null, fonte: "sem espaçamento na base" };
    return { qtd: Math.ceil(A / (e[0] * e[1]) - 1e-9), densidade_m2: 1 / (e[0] * e[1]), unidade: linha ? "plantas (semeadura direta)" : "mudas", espacamento: e, fonte: planta.espacamento.fonte || "" };
  }
  function mudas(planta, area_m2, densidade) { return mudasInfo(planta, area_m2, densidade).qtd; }

  /* ───────────── consórcios ───────────── */
  function criteriosDe(o) {
    return {
      bioma: o.bioma || "", uf: o.uf || "", regiao: o.regiao || "", zonaAmortecimento: !!o.zonaAmortecimento,
      altitude_m: o.altitude_m, irrigacao: !!o.irrigacao, luz: o.luz || "",
      solo: Object.assign({}, o.solo || {}), clima: Object.assign({}, o.clima || {}),
      incluirInvasoras: false, incluirViveiro: false
    };
  }
  function pontuar(p, escolhidas, ctx) {
    let s = 0;
    s += ctx.fun.filter(f => temFun(p, f)).length;
    s += 2.5 * escolhidas.filter(e => companheiras(p, e)).length;
    if (nativaDe(p, ctx.bioma)) s += ctx.precisaNativa() ? 4 : 1;
    if (ctx.acido && p.solo && p.solo.acido) s += 0.5;
    const cf = p.espacamento && p.espacamento.confianca; s += cf === "alta" ? 0.3 : cf === "media" ? 0.15 : 0;
    if (ctx.pref) s += ctx.pref(p) || 0;
    const g = genero(p); if (g && escolhidas.some(e => genero(e) === g)) s -= 3;   /* diversidade: evita dois do mesmo gênero */
    return s;
  }
  /* escolhe k espécies de cands, uma a uma, pela maior pontuação, sem antagonistas das já escolhidas */
  function escolher(cands, k, escolhidas, ctx, motivo) {
    const out = [];
    for (let i = 0; i < k; i++) {
      let melhor = null, ms = -Infinity;
      for (const p of cands) {
        if (escolhidas.some(e => e.n === p.n) || out.some(e => e.n === p.n)) continue;
        if (escolhidas.concat(out).some(e => antagonistas(p, e))) continue;
        const s = pontuar(p, escolhidas.concat(out), ctx);
        if (s > ms || (s === ms && melhor && p.n < melhor.n)) { ms = s; melhor = p; }
      }
      if (!melhor) break;
      melhor = Object.assign({}, melhor); out.push(melhor); ctx.marcar(melhor);
      melhor.__motivo = motivo ? motivo(melhor, escolhidas.concat(out)) : "";
    }
    return out;
  }
  function porque(p, juntas, ctx) {
    const r = [];
    const f = ctx.fun.filter(x => temFun(p, x)); if (f.length) r.push("funções: " + f.map(nomeFuncao).join(", "));
    const c = juntas.filter(e => e.n !== p.n && companheiras(p, e)).map(e => e.nome); if (c.length) r.push("combina com " + c.slice(0, 3).join(", "));
    if (nativaDe(p, ctx.bioma)) r.push("nativa" + (ctx.bioma ? " do bioma" : ""));
    return r.join("; ");
  }
  const NOMES_FUN = { ar: "filtra o ar", agua: "filtra a água", solo: "recupera o solo", barranco: "segura barranco", nitrogenio: "fixa nitrogênio", biomassa: "biomassa", polinizadores: "polinizadores", alimento: "alimento", animais: "alimento para animais", protecao: "proteção", oleo: "óleo", medicinal: "medicinal", sombra: "sombra", ornamental: "flores", madeira: "madeira" };
  function nomeFuncao(id) { const f = BASE && !Array.isArray(BASE) && Array.isArray(BASE.funcoes) && BASE.funcoes.find(x => x.id === id); return NOMES_FUN[id] || (f ? f.nome : id); }

  function novoCtx(o, objetivo, plantas) {
    const alvo = o.nativas_pct == null ? ALVO_NATIVAS[objetivo] : clamp(+o.nativas_pct || 0, 0, 100);
    const ctx = {
      bioma: semBioma(o.bioma) ? "" : o.bioma, fun: OBJETIVOS[objetivo].fun, acido: !!(o.solo && o.solo.acido), alvoNativas: alvo, escolhidas: [],
      marcar(p) { this.escolhidas.push(p); },
      precisaNativa() { const t = this.escolhidas.length; if (!t) return alvo > 0; return this.escolhidas.filter(x => nativaDe(x, this.bioma)).length / t * 100 < alvo; }
    };
    return ctx;
  }
  function item(p, estrato, qtd, cobertura_pct, extra) {
    const e = esp(p), linha = p.espacamento && /linha/.test(p.espacamento.forma || "");
    return Object.assign({
      n: p.n, nome: p.nome, cientifico: p.cientifico, estrato, ciclo: p.ciclo, nativa: false, grupo: p.grupo_restauracao || null,
      mudas: qtd, unidade: linha ? "plantas (semeadura direta)" : "mudas", espacamento: e, cobertura_pct, motivo: p.__motivo || ""
    }, extra || {});
  }
  function semCabe(p, areaDisp) { const a = areaPlanta(p); return a != null && a <= areaDisp * 2; }   /* cabe ao menos ~meia planta */

  function montarAgrofloresta(o, plantas, res) {
    const A = res.area_m2, crit = criteriosDe(o), ctx = novoCtx(o, "agrofloresta", plantas);
    const arido = !o.irrigacao && num(o.clima && o.clima.meses_secos) >= 7;
    const fator = arido ? 0.7 : 1;
    if (arido) res.explicacao.push("Clima com 7 meses secos ou mais e sem irrigação: a cobertura de cada estrato foi reduzida em 30% para as plantas não disputarem a pouca água.");
    const k = A < 50 ? { emergente: 0, alto: 1, medio: 1, baixo: 2, rasteiro: 1 } : A < 300 ? { emergente: 1, alto: 1, medio: 2, baixo: 3, rasteiro: 2 } : { emergente: 1, alto: 2, medio: 3, baixo: 3, rasteiro: 2 };
    const fora = /^(Interior|Bambu|Flor|Muda \(viveiro\))$/;
    const pool = filtrar(plantas, crit).filter(p => ESTRATOS_SAF.includes(p.estrato) && !fora.test(p.tipo || "") && esp(p));
    const porEst = {};
    /* sob as copas, os estratos médio e baixo preferem quem aguenta meia-sombra; no clima seco, quem tolera seca */
    ctx.pref = p => (["medio", "baixo", "rasteiro"].includes(p.estrato) && /sombra/.test(p.luz || "") ? 1 : 0)
      + (A >= 100 && areaPlanta(p) < 0.1 ? -2 : 0)   /* hortaliça miúda em área grande vira milhares de mudas: fica para a horta */
      + (p.estrato === "rasteiro" && (temFun(p, "solo") || temFun(p, "nitrogenio") || /Cobertura de solo|Adubo verde/.test(p.tipo || "")) ? 1.5 : 0) + (arido && p.solo && p.solo.seco ? 1.5 : 0) + prefVegetacao(p, o.vegetacao);
    for (const s of ESTRATOS_SAF) {
      const cob = COBERTURA[s].alvo * fator;
      const cands = pool.filter(p => p.estrato === s && semCabe(p, A * cob / 100 / Math.max(1, k[s])));
      porEst[s] = escolher(cands, k[s], ctx.escolhidas.slice(0, -0 || undefined), ctx, (p, j) => porque(p, j, ctx));
      if (k[s] && !porEst[s].length) res.explicacao.push(`Estrato ${NOME_ESTRATO[s].toLowerCase()}: nenhuma espécie da base serve para este lugar e cabe em ${Math.round(A)} m²; o estrato fica vazio.`);
    }
    /* sucessão: cada fase precisa de pelo menos uma espécie */
    for (const c of CICLOS) {
      if (ctx.escolhidas.some(p => p.ciclo === c)) continue;
      const cands = pool.filter(p => p.ciclo === c && semCabe(p, A * COBERTURA[p.estrato].alvo * fator / 100 / Math.max(1, (porEst[p.estrato] || []).length + 1)));
      const e = escolher(cands, 1, ctx.escolhidas.slice(), ctx, (p, j) => "completa a sucessão (" + NOME_CICLO[c] + "); " + porque(p, j, ctx));
      if (e.length) { porEst[e[0].estrato].push(e[0]); }
      else res.explicacao.push(`Sucessão: não há espécie da fase ${NOME_CICLO[c]} que sirva aqui.`);
    }
    /* adubadeira: pelo menos uma fixadora de nitrogênio */
    if (!ctx.escolhidas.some(p => temFun(p, "nitrogenio"))) {
      const cands = pool.filter(p => temFun(p, "nitrogenio") && semCabe(p, A * COBERTURA[p.estrato].alvo * fator / 100 / Math.max(1, (porEst[p.estrato] || []).length + 1)));
      const e = escolher(cands, 1, ctx.escolhidas.slice(), ctx, (p, j) => "adubadeira (fixa nitrogênio); " + porque(p, j, ctx));
      if (e.length) porEst[e[0].estrato].push(e[0]);
    }
    for (const s of ESTRATOS_SAF) {
      const ps = porEst[s] || []; if (!ps.length) continue;
      const cob = COBERTURA[s].alvo * fator / ps.length;
      for (const p of ps) { const q = Math.max(1, Math.round(A * cob / 100 / areaPlanta(p))); res.itens.push(item(p, s, q, null)); }
    }
    res.limites = Object.fromEntries(ESTRATOS_SAF.map(s => [s, { min: COBERTURA[s].min * fator, max: COBERTURA[s].max * fator, alvo: COBERTURA[s].alvo * fator }]));
    res.explicacao.unshift("Agrofloresta em camadas: cada estrato (emergente, alto, médio, baixo e rasteiro) ocupa a sua parte do espaço e da luz, e as fases da sucessão (placenta I e II, secundária e clímax) se substituem com os anos. As espécies foram escolhidas pelas funções, pelas companheiras e pela preferência por nativas.");
  }

  function montarHorta(o, plantas, res) {
    const A = res.area_m2, util = A * AREA_UTIL_HORTA, crit = criteriosDe(o), ctx = novoCtx(o, "horta", plantas);
    const tiposOk = /^(Hortaliça\/PANC|Cultivo alimentar|Aromática|Erva medicinal|Planta de proteção|Flor)$/;
    const pool = filtrar(plantas, crit).filter(p => ["baixo", "rasteiro", "trepadeira"].includes(p.estrato) && ["placenta1", "placenta2"].includes(p.ciclo) && tiposOk.test(p.tipo || "") && esp(p) && areaPlanta(p) <= Math.max(1, util / 4));
    const kTotal = clamp(Math.round(A / 3), 4, 10);
    /* variedade na mesa: folha, raiz, fruto e grão antes de repetir o grupo */
    ctx.pref = p => { const g = grupoHorta(p); return g && !ctx.escolhidas.some(e => grupoHorta(e) === g) ? 2 : 0; };
    const grupos = [];
    const add = (cands, k, rot, part) => { const e = escolher(cands, k, ctx.escolhidas.slice(), ctx, (p, j) => rot + "; " + porque(p, j, ctx)); if (e.length) grupos.push({ itens: e, part }); return e.length; };
    let usados = 0, parte = 0;
    if (A >= 8) { usados += add(pool.filter(p => p.estrato === "trepadeira" && p.tipo !== "Flor"), 1, "trepadeira no tutor ou na cerca", 0.10); parte += usados ? 0.10 : 0; }
    let u = add(pool.filter(p => temFun(p, "protecao") && p.tipo !== "Cultivo alimentar"), 1, "bordadura de proteção (afasta pragas, atrai inimigos naturais)", 0.06); usados += u; parte += u ? 0.06 : 0;
    u = add(pool.filter(p => p.tipo === "Aromática" || p.tipo === "Erva medicinal"), 1, "aromática ou medicinal", 0.09); usados += u; parte += u ? 0.09 : 0;
    const resto = Math.max(1, kTotal - usados);
    const alim = pool.filter(p => /^(Hortaliça\/PANC|Cultivo alimentar)$/.test(p.tipo || "") && p.estrato !== "trepadeira");
    add(alim, resto, "alimento", 1 - parte);
    for (const g of grupos) {
      const fr = g.part / g.itens.length;
      for (const p of g.itens) { const q = Math.max(1, Math.round(util * fr / areaPlanta(p))); res.itens.push(item(p, p.estrato, q, null, { area_m2: +(util * fr).toFixed(2) })); }
    }
    res.explicacao.unshift(`Horta em canteiros: ${Math.round(AREA_UTIL_HORTA * 100)}% da área vira canteiro (${util.toFixed(1).replace(".", ",")} m²) e o resto é caminho. Cada espécie recebe um pedaço do canteiro e as mudas saem do espaçamento recomendado. Pares que se atrapalham (por exemplo feijão com cebola ou alho, tomate com batata) não entram juntos.`);
    res.explicacao.push("Depois de cada colheita, troque a família no canteiro (rotação) e, no inverno ou na entressafra, semeie adubo verde.");
  }

  const GRUPOS_HORTA = [
    ["folha", /Lactuca|Brassica|Spinacia|Beta vulgaris|Nasturtium|Basella|Tetragonia|Eryngium|Acmella|Rumex|Talinum|Portulaca|Xanthosoma taioba|Cichorium/],
    ["raiz", /Daucus|Solanum tuberosum|Ipomoea|Arracacia|Allium|Manihot|Maranta|Dioscorea|Xanthosoma riedelianum|Zingiber|Colocasia|Smallanthus/],
    ["fruto", /Solanum lycopersicum|Capsicum|Cucurbita|Cucumis|Solanum melongena|Abelmoschus|Physalis|Fragaria|Solanum sessiliflorum|Citrullus|Sechium/],
    ["grao", /Phaseolus|Pisum|Vigna|Vicia faba|Zea|Cicer|Arachis hypogaea|Amaranthus/]];
  function grupoHorta(p) { const g = GRUPOS_HORTA.find(([, re]) => re.test(p.cientifico || "")); return g ? g[0] : null; }

  function montarPomar(o, plantas, res) {
    const A = res.area_m2, crit = criteriosDe(o), ctx = novoCtx(o, "pomar", plantas);
    const pool = filtrar(plantas, crit).filter(p => esp(p) && !/^(Interior|Bambu)$/.test(p.tipo || ""));
    const kF = clamp(Math.round(A / 50), 2, 8);
    const frut = pool.filter(p => (p.tipo === "Frutífera" || (temFun(p, "alimento") && /^(Árvore nativa|Cultivo agroflorestal)$/.test(p.tipo || ""))) && ["alto", "medio", "baixo"].includes(p.estrato) && ["secundaria", "climax", "placenta2"].includes(p.ciclo) && semCabe(p, A * 0.6 / kF));
    const fr = escolher(frut, kF, [], ctx, (p, j) => "frutífera; " + porque(p, j, ctx));
    const adub = escolher(pool.filter(p => temFun(p, "nitrogenio") && ["baixo", "medio"].includes(p.estrato) && semCabe(p, A * 0.1)), 1, ctx.escolhidas.slice(), ctx, (p, j) => "adubadeira entre as frutíferas (fixa nitrogênio, poda vira adubo); " + porque(p, j, ctx));
    const cob = escolher(pool.filter(p => p.estrato === "rasteiro" && (temFun(p, "solo") || temFun(p, "nitrogenio") || /Cobertura de solo|Adubo verde/.test(p.tipo || ""))), 1, ctx.escolhidas.slice(), ctx, (p, j) => "cobertura viva do chão (no lugar do capim); " + porque(p, j, ctx));
    fr.forEach(p => res.itens.push(item(p, p.estrato, Math.max(1, Math.round(A * 0.6 / fr.length / areaPlanta(p))), null)));
    adub.forEach(p => res.itens.push(item(p, p.estrato, Math.max(1, Math.round(A * 0.1 / areaPlanta(p))), null)));
    cob.forEach(p => res.itens.push(item(p, p.estrato, Math.max(1, Math.round(A * 0.7 / areaPlanta(p))), null)));
    res.limites = { alto: { min: 0, max: 70, alvo: 60 }, medio: { min: 0, max: 70, alvo: 60 }, baixo: { min: 0, max: 90, alvo: 60 }, rasteiro: { min: 40, max: 100, alvo: 70 } };
    res.explicacao.unshift(`Pomar: as frutíferas ocupam cerca de 60% da área com as copas adultas, cada uma no espaçamento recomendado; uma adubadeira fixa nitrogênio e a cobertura viva protege o solo.`);
  }

  function montarRestauracao(o, plantas, res) {
    const A = res.area_m2, crit = criteriosDe(o), ctx = novoCtx(o, "restauracao_app", plantas);
    let alvo = o.nativas_pct == null ? 100 : clamp(+o.nativas_pct || 0, 0, 100);
    if (alvo < NATIVAS_MIN_APP) { res.violacoes.push({ regra: "nativas_minimo", nivel: "erro", texto: `Pediu ${alvo}% de nativas; em APP o mínimo é ${NATIVAS_MIN_APP}% (Lei 12.651/2012, art. 61-A, e só em pequena propriedade). Usado ${NATIVAS_MIN_APP}%.` }); alvo = NATIVAS_MIN_APP; }
    ctx.alvoNativas = alvo;
    ctx.pref = p => prefVegetacao(p, o.vegetacao) + (o.solo && o.solo.umido && p.solo && p.solo.umido ? 1 : 0);
    if (campestre(o.vegetacao)) res.violacoes.push({ regra: "vegetacao_campestre", nivel: "aviso", texto: `Vegetação original do lugar: ${o.vegetacao}. Em campo nativo, restaure o campo (manejo, sementes de capins e ervas nativas) e plante árvores só nas matas ciliares e capões; não cubra o campo de árvores.` });
    crit.app = true;
    if (alvo >= 100) crit.somenteNativas = true;
    const pool = filtrar(plantas, crit).filter(p => ["emergente", "alto", "medio", "baixo"].includes(p.estrato) && p.grupo_restauracao);
    const nEsp = A >= 10000 ? 30 : A >= 3000 ? 20 : A >= 1000 ? 12 : A >= 300 ? 8 : 5;
    const dens = num(o.densidade) > 0 ? num(o.densidade) : 1 / (GRADE_RESTAURACAO[0] * GRADE_RESTAURACAO[1]);
    const total = Math.max(2, Math.ceil(A * dens - 1e-9));
    const nativos = q => q.filter(p => nativaDe(p, ctx.bioma));
    const pre = pool.filter(p => p.grupo_restauracao === "preenchimento"), div = pool.filter(p => p.grupo_restauracao === "diversidade");
    const ordenaNat = arr => alvo >= 100 ? nativos(arr) : arr;
    const kPre = Math.ceil(nEsp / 2), kDiv = nEsp - kPre;
    const ePre = escolher(ordenaNat(pre), kPre, [], ctx, (p, j) => "preenchimento: cresce rápido e cobre o solo; " + porque(p, j, ctx));
    const eDiv = escolher(ordenaNat(div), kDiv + Math.max(0, kPre - ePre.length), ctx.escolhidas.slice(), ctx, (p, j) => "diversidade: cresce devagar e forma a mata madura; " + porque(p, j, ctx));
    let nPre = ePre.length && eDiv.length ? Math.round(total / 2) : (ePre.length ? total : 0), nDiv = total - nPre;
    if (!ePre.length || !eDiv.length) res.violacoes.push({ regra: "app_grupos", nivel: "aviso", texto: "Faltam espécies de um dos grupos (preenchimento ou diversidade) para este lugar; a proporção 50/50 não foi possível." });
    const distribuir = (arr, tot, g) => arr.forEach((p, i) => { const q = Math.floor(tot / arr.length) + (i < tot % arr.length ? 1 : 0); if (q > 0) res.itens.push(item(p, p.estrato, q, null, { grupo: g, espacamento: [GRADE_RESTAURACAO[1], GRADE_RESTAURACAO[0]] })); });
    distribuir(ePre, nPre, "preenchimento"); distribuir(eDiv, nDiv, "diversidade");
    res.grade_m = GRADE_RESTAURACAO.slice();
    res.explicacao.unshift(`Restauração de APP pelo modelo de linhas alternadas: uma linha de espécies de preenchimento (pioneiras que crescem rápido, sombreiam e abafam o capim) e uma de diversidade (secundárias tardias e clímax, que formam a mata madura). Metade das mudas de cada grupo, em grade de ${GRADE_RESTAURACAO[0]} × ${GRADE_RESTAURACAO[1]} m (cerca de 1.667 mudas por hectare), só com espécies nativas${ctx.bioma ? " do bioma " + ctx.bioma : ""}.`);
    if (o.solo && o.solo.umido) res.explicacao.push("Beira de rio: entram só espécies que toleram solo encharcado. Pelo Código Florestal (Lei 12.651/2012, art. 4º, I), a faixa mínima de APP é de 30 m para rios com menos de 10 m de largura.");
    res.explicacao.push("Manutenção: coroamento e controle do capim por 2 anos, combate a formigas, replantio das falhas (5–10%). Quanto mais espécies, melhor: nenhuma deve passar de 20% das mudas.");
  }

  function montarJardimChuva(o, plantas, res) {
    const A = res.area_m2, crit = criteriosDe(o), ctx = novoCtx(o, "jardim_chuva", plantas);
    crit.solo = Object.assign({}, crit.solo, { umido: true, seco: false });
    crit.irrigacao = true;   /* recebe a água do telhado e do piso: a chuva do lugar não limita */
    const pool = filtrar(plantas, crit).filter(p => ["aquatica", "baixo", "rasteiro"].includes(p.estrato) && esp(p) && areaPlanta(p) <= 1.5 && p.tipo !== "Interior" && p.tipo !== "Cultivo alimentar");
    const k = clamp(Math.round(A / 4), 3, 6), kc = Math.ceil(k / 2), kb = k - kc;
    const centro = escolher(pool.filter(p => p.estrato === "aquatica" || temFun(p, "agua")), kc, [], ctx, (p, j) => "centro (fica alagado depois da chuva); " + porque(p, j, ctx));
    const bordaCands = pool.filter(p => p.solo && p.solo.seco);
    const borda = escolher(bordaCands.length ? bordaCands : pool, kb, ctx.escolhidas.slice(), ctx, (p, j) => "borda (aguenta alagar e secar); " + porque(p, j, ctx));
    centro.forEach(p => res.itens.push(item(p, p.estrato, Math.max(1, Math.round(A * 0.6 / centro.length / areaPlanta(p))), null, { zona: "centro" })));
    borda.forEach(p => res.itens.push(item(p, p.estrato, Math.max(1, Math.round(A * 0.4 / borda.length / areaPlanta(p))), null, { zona: "borda" })));
    res.explicacao.unshift("Jardim de chuva: uma depressão de 10 a 20 cm com solo que drena, que recebe a água do telhado ou do piso e a deixa infiltrar em até 48 horas. No centro, plantas que aguentam ficar alagadas; na borda, plantas que aguentam alagar e secar. Precisa de um extravasor para a chuva forte.");
  }

  /* vegetação original (IBGE, ui.gisX.zonas.vegetacao.nm_pretet): florestas úmidas preferem espécies de solo úmido;
     florestas estacionais e savana-estépica preferem as que toleram seca */
  function prefVegetacao(p, veg) {
    const v = semAcento(veg); if (!v || !p.solo) return 0;
    if (/ombrofila|campinarana|formacoes pioneiras/.test(v)) return p.solo.umido ? 0.8 : (p.solo.seco ? -0.5 : 0);
    if (/estacional|savana-estepica|savana estepica|caatinga|estepe|chaco/.test(v)) return p.solo.seco ? 0.8 : -0.3;
    if (/savana|cerrado/.test(v)) return p.solo.seco ? 0.5 : 0;
    return 0;
  }
  const campestre = veg => { const v = semAcento(veg); return !!v && /estepe|campo|savana gramineo|savana parque|gramineo-lenhosa|refugio/.test(v) && !/florestada|arborizada/.test(v); };

  /* opções: { area_m2, bioma, solo, clima, luz, altitude_m, irrigacao, objetivo, nativas_pct, densidade, plantas } */
  function montarConsorcio(opcoes, plantasArg) {
    const o = Object.assign({}, opcoes || {}), plantas = plantasDe(plantasArg || o.plantas);
    const objetivo = OBJETIVOS[o.objetivo] ? o.objetivo : "agrofloresta";
    const res = { objetivo, nome: OBJETIVOS[objetivo].nome, area_m2: Math.max(0, num(o.area_m2) || 0), bioma: o.bioma || "", criterios: criteriosDe(o), nativas_alvo_pct: null,
      itens: [], explicacao: [], violacoes: [], limites: null, estratos: {}, sucessao: {}, total_mudas: 0, nativas_pct_especies: 0, nativas_pct_mudas: 0 };
    if (!res.area_m2) { res.violacoes.push({ regra: "area", nivel: "erro", texto: "Informe a área (m²)." }); return res; }
    if (!plantas.length) { res.violacoes.push({ regra: "base", nivel: "erro", texto: "Base de plantas não carregada." }); return res; }
    ({ agrofloresta: montarAgrofloresta, horta: montarHorta, pomar: montarPomar, restauracao_app: montarRestauracao, jardim_chuva: montarJardimChuva })[objetivo](o, plantas, res);
    res.nativas_alvo_pct = o.nativas_pct == null ? ALVO_NATIVAS[objetivo] : clamp(+o.nativas_pct || 0, 0, 100);
    if (objetivo === "restauracao_app") res.nativas_alvo_pct = Math.max(NATIVAS_MIN_APP, res.nativas_alvo_pct);
    resumir(res);
    res.violacoes = res.violacoes.concat(verificar(res, plantas, res.criterios));
    if (!res.itens.length) res.violacoes.push({ regra: "vazio", nivel: "erro", texto: "Nenhuma espécie da base serve para estas condições." });
    return res;
  }
  function resumir(res) {
    const A = res.area_m2, P = new Map(plantasDe().map(p => [p.n, p]));
    res.itens.forEach(it => { const p = P.get(it.n) || {}; it.nativa = nativaDe(p, res.bioma); const e = it.espacamento || esp(p); it.cobertura_pct = e ? +(it.mudas * e[0] * e[1] / A * 100).toFixed(1) : null; });
    res.estratos = {};
    res.itens.forEach(it => { const s = res.estratos[it.estrato] = res.estratos[it.estrato] || { especies: 0, mudas: 0, cobertura_pct: 0 }; s.especies++; s.mudas += it.mudas; s.cobertura_pct = +(s.cobertura_pct + (it.cobertura_pct || 0)).toFixed(1); });
    if (res.limites) Object.entries(res.limites).forEach(([s, l]) => { if (res.estratos[s]) Object.assign(res.estratos[s], { min: l.min, max: l.max, alvo: l.alvo }); });
    res.sucessao = {}; res.itens.forEach(it => { (res.sucessao[it.ciclo || "?"] = res.sucessao[it.ciclo || "?"] || []).push(it.n); });
    res.total_mudas = res.itens.reduce((t, it) => t + it.mudas, 0);
    res.nativas_pct_especies = res.itens.length ? Math.round(res.itens.filter(i => i.nativa).length / res.itens.length * 100) : 0;
    res.nativas_pct_mudas = res.total_mudas ? Math.round(res.itens.filter(i => i.nativa).reduce((t, i) => t + i.mudas, 0) / res.total_mudas * 100) : 0;
    res.explicacao.push(`Resultado: ${res.itens.length} espécies e ${res.total_mudas} mudas ou plantas; nativas: ${res.nativas_pct_especies}% das espécies e ${res.nativas_pct_mudas}% das mudas (alvo ${res.nativas_alvo_pct}%).`);
  }

  /* confere as regras num consórcio (o montado aqui ou um digitado): devolve [{regra, nivel, texto}] */
  function verificar(res, plantasArg, criterios) {
    const P = new Map(plantasDe(plantasArg).map(p => [p.n, p])), v = [], its = (res && res.itens) || [];
    const ps = its.map(i => P.get(i.n)).filter(Boolean);
    its.forEach(i => { if (!P.get(i.n)) v.push({ regra: "planta", nivel: "erro", texto: `Planta nº ${i.n} não existe na base.` }); });
    ps.forEach(p => { if (p.invasora) v.push({ regra: "invasora", nivel: "erro", texto: `${p.nome} é invasora.` }); if (!eEspecie(p)) v.push({ regra: "viveiro", nivel: "erro", texto: `${p.nome} é item de viveiro, não espécie.` }); if (!esp(p)) v.push({ regra: "espacamento", nivel: "erro", texto: `${p.nome} sem espaçamento na base.` }); });
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) if (antagonistas(ps[i], ps[j])) v.push({ regra: "antagonistas", nivel: "erro", texto: `${ps[i].nome} e ${ps[j].nome} se atrapalham (antagonistas).` });
    if (criterios) ps.forEach(p => { const m = avaliar(p, Object.assign({}, criterios, { incluirInvasoras: true })); if (m.length) v.push({ regra: "filtro", nivel: "erro", texto: `${p.nome}: ${m.join("; ")}.` }); });
    its.forEach(i => { if (!(i.mudas > 0)) v.push({ regra: "mudas", nivel: "erro", texto: `${i.nome}: quantidade de mudas zerada.` }); });
    if (res && res.estratos) Object.entries(res.estratos).forEach(([s, e]) => { if (e.min != null && (e.cobertura_pct < e.min - 0.05 || e.cobertura_pct > e.max + 0.05)) v.push({ regra: "cobertura", nivel: "aviso", texto: `Estrato ${(NOME_ESTRATO[s] || s).toLowerCase()} com ${String(e.cobertura_pct).replace(".", ",")}% de cobertura (limites ${Math.round(e.min)}–${Math.round(e.max)}%).` }); });
    if (res && res.objetivo === "agrofloresta") CICLOS.forEach(c => { if (!ps.some(p => p.ciclo === c)) v.push({ regra: "sucessao", nivel: "aviso", texto: `Sucessão incompleta: falta a fase ${NOME_CICLO[c]}.` }); });
    if (res && res.nativas_alvo_pct != null && ps.length) {
      const pct = res.nativas_pct_especies;
      if (pct < res.nativas_alvo_pct) v.push({ regra: "nativas", nivel: res.objetivo === "restauracao_app" ? "erro" : "aviso", texto: `Nativas: ${pct}% das espécies, abaixo do alvo de ${res.nativas_alvo_pct}% (faltam nativas na base para estas condições).` });
    }
    if (res && res.objetivo === "restauracao_app" && res.total_mudas) {
      const pre = its.filter(i => i.grupo === "preenchimento").reduce((t, i) => t + i.mudas, 0) / res.total_mudas * 100;
      if (pre < 40 || pre > 60) v.push({ regra: "app_proporcao", nivel: "aviso", texto: `Preenchimento com ${Math.round(pre)}% das mudas (o clássico é 50%, aceitável de 40 a 60%).` });
      if (its.length >= 5) its.forEach(i => { if (i.mudas / res.total_mudas > 0.2 + 1e-9) v.push({ regra: "app_dominancia", nivel: "aviso", texto: `${i.nome} com ${Math.round(i.mudas / res.total_mudas * 100)}% das mudas (máximo recomendado 20%).` }); });
    }
    return v;
  }

  /* ───────────── combinações antigas (espacos[].combinacoes A/B/C) ───────────── */
  function partesNome(nome) {
    const s = semAcento(nome), fora = s.replace(/\(.*?\)/g, " ").trim(), dentro = (s.match(/\((.*?)\)/) || [, ""])[1];
    const ps = new Set([s, fora, dentro].filter(Boolean));
    [fora, dentro].forEach(t => t.split(/\s*(?:,|\/|\be\b)\s*/).map(x => x.trim()).filter(Boolean).forEach(x => ps.add(x)));
    return ps;
  }
  function acharPlanta(nome, plantasArg) {
    const k = semAcento(nome).replace(/\s*[.;]$/, ""); if (!k) return null;
    const ps = plantasDe(plantasArg);
    const exato = ps.find(p => semAcento(p.nome) === k); if (exato) return exato;
    const semPar = ps.find(p => semAcento(p.nome).replace(/\s*\(.*?\)\s*/g, " ").trim() === k || (semAcento(p.nome).match(/\((.*?)\)/) || [, "§"])[1] === k);
    if (semPar) return semPar;
    const cands = ps.filter(p => eEspecie(p) && partesNome(p.nome).has(k));
    if (cands.length) return cands.sort((a, b) => partesNome(a.nome).size - partesNome(b.nome).size || a.n - b.n)[0];
    return null;   /* sem "começa com": evita feijão → feijão-guandu */
  }
  /* "4 × Biri (cana-índica), 2 × Papiro-brasileiro" → itens [[n, qtd]].
     "3 × Alho-poró + cenoura, … → 134 cenoura, beterraba, rabanete, 32 cebolinha" → módulos (antes da seta) e plantas (depois). */
  function corrigirCombinacao(texto, plantasArg) {
    const r = { itens: [], modulos: [], nao_achados: [], avisos: [] };
    let t = String(texto == null ? "" : texto).trim(); if (!t || t === "—" || t === "-") return r;
    const [antes0, depois] = t.split(/\s*(?:→|->)\s*/);
    const antes = antes0.replace(/^[^:\d×]{3,}:\s*/, "");
    const soma = (p, q) => { const j = r.itens.find(x => x[0] === p.n); if (j) j[1] += q; else r.itens.push([p.n, q]); };
    antes.split(/,\s*(?=\d+\s*[×x]\s)/).forEach(seg => {
      const m = seg.trim().match(/^(\d+)\s*[×x]\s*(.+)$/); if (!m) { if (seg.trim()) r.avisos.push("trecho sem quantidade: " + seg.trim()); return; }
      const q = +m[1], nome = m[2].trim();
      if (depois != null || /\s\+\s|^m[oó]dulo\b/i.test(nome)) { r.modulos.push({ qtd: q, nome }); return; }
      const p = acharPlanta(nome, plantasArg); if (p) { if (q > 0) soma(p, q); } else r.nao_achados.push(nome);
    });
    if (depois != null) {
      const grupos = [];
      depois.split(",").map(x => x.trim()).filter(Boolean).forEach(tok => { const m = tok.match(/^(\d+)\s+(.+)$/); if (m) grupos.push({ q: +m[1], nome: m[2] }); else if (grupos.length) grupos[grupos.length - 1].nome += ", " + tok; else r.avisos.push("trecho sem quantidade: " + tok); });
      grupos.forEach(g => { if (!(g.q > 0)) return; const p = acharPlanta(g.nome, plantasArg); if (p) soma(p, g.q); else r.nao_achados.push(g.nome); });
    }
    return r;
  }

  /* ───────────── terreno do Planejador ───────────── */
  const TIPOS_TERRENO = {
    horta: { tipo: "horta_pomar", nome: "Horta ou pomar" }, gramado: { tipo: "jardim", nome: "Gramado ou jardim" },
    mata: { tipo: "mata", nome: "Mata preservada" }, infiltracao: { tipo: "jardim_chuva", nome: "Vala ou jardim de infiltração" }
  };
  function lerJson(x) { if (!x) return null; if (typeof x === "object") return x; try { return JSON.parse(x); } catch (e) { return null; } }
  function areaPoly(P) { let a = 0; for (let i = 0; i < P.length; i++) { const p = P[i], q = P[(i + 1) % P.length]; a += p[0] * q[1] - q[0] * p[1]; } return Math.abs(a) / 2; }
  function dentroPoly(pt, P) { let d = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, yi] = P[i], [xj, yj] = P[j]; if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) d = !d; } return d; }
  function dentroItem(pt, it) { const r = (num(it.rot) || 0) * Math.PI / 180, c = Math.cos(r), s = Math.sin(r), dx = pt[0] - it.x, dy = pt[1] - it.y, a = dx * c + dy * s, b = -dx * s + dy * c; return Math.abs(a) <= it.w / 2 && Math.abs(b) <= it.d / 2; }
  /* declividade > 100% (45°): mesma ideia do Planejador (IDW dos pontos cotados numa grade), mais grossa */
  function declividadeApp(t) {
    const poly = (t && t.poly) || []; let P = ((t && t.pontos) || []).filter(p => Array.isArray(p) && p.length >= 3 && isFinite(p[2]));
    if (poly.length < 3 || P.length < 3) return null;
    if (P.length > 1500) { const k = Math.ceil(P.length / 1500); P = P.filter((_, i) => i % k === 0); }
    const xs = poly.map(p => p[0]), ys = poly.map(p => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys), W = Math.max(...xs) - x0, H = Math.max(...ys) - y0;
    const n = 40, cs = Math.max(W, H) / n || 1, nx = Math.ceil(W / cs) + 1, ny = Math.ceil(H / cs) + 1, Z = new Float64Array(nx * ny);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const x = x0 + i * cs, y = y0 + j * cs, best = [];
      for (const q of P) { const d = Math.hypot(q[0] - x, q[1] - y); if (best.length < 8) { best.push([d, q[2]]); best.sort((a, b) => a[0] - b[0]); } else if (d < best[7][0]) { best[7] = [d, q[2]]; best.sort((a, b) => a[0] - b[0]); } }
      if (best[0][0] < 1e-6) { Z[j * nx + i] = best[0][1]; continue; }
      let s = 0, w = 0; best.forEach(([d, z]) => { const k = 1 / (d * d); s += k * z; w += k; }); Z[j * nx + i] = s / w;
    }
    const g = (i, j) => Z[clamp(j, 0, ny - 1) * nx + clamp(i, 0, nx - 1)], cel = []; let dentro = 0;
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const pt = [x0 + i * cs, y0 + j * cs]; if (!dentroPoly(pt, poly)) continue; dentro++;
      const dx = (g(i + 1, j) - g(i - 1, j)) / (2 * cs), dy = (g(i, j + 1) - g(i, j - 1)) / (2 * cs);
      if (Math.hypot(dx, dy) * 100 > 100) cel.push(pt);
    }
    return { cs, celulas: cel, area_m2: cel.length * cs * cs, fracao: dentro ? cel.length / dentro : 0 };
  }
  function objetivoSugerido(tipo, area) {
    if (tipo === "jardim_chuva") return "jardim_chuva";
    if (tipo === "mata" || tipo === "app") return "restauracao_app";
    if (tipo === "horta_pomar") return area <= 60 ? "horta" : area <= 400 ? "pomar" : "agrofloresta";
    if (tipo === "jardim") return "agrofloresta";
    return null;
  }
  /* localStorage "physis.terreno.v1" (schema physis.terreno/1.0) → [{id, nome, tipo, area_m2, app, area_app_m2, objetivo}] */
  function lerTerreno(localStorageJson) {
    const S = lerJson(localStorageJson); if (!S || !Array.isArray(S.itens)) return [];
    const dec = declividadeApp(S.terreno), out = [];
    S.itens.forEach((it, k) => {
      const T = TIPOS_TERRENO[it.tipo]; if (!T) return;
      const w = num(it.w) || 0, d = num(it.d) || 0, area = w * d; if (!(area > 0)) return;
      const ii = { x: num(it.x) || 0, y: num(it.y) || 0, w, d, rot: it.rot };
      const nApp = dec ? dec.celulas.filter(pt => dentroItem(pt, ii)).length : 0;
      const area_app = Math.min(area, nApp * (dec ? dec.cs * dec.cs : 0));
      out.push({ id: String(it.id != null ? it.id : "item-" + k), nome: it.nome || T.nome, tipo: T.tipo, area_m2: +area.toFixed(2), app: nApp > 0, area_app_m2: +area_app.toFixed(1), objetivo: nApp > 0 ? "restauracao_app" : objetivoSugerido(T.tipo, area), preservar: T.tipo === "mata",
        forma: "ret", x: ii.x, y: ii.y, w, d, rot: num(it.rot) || 0, origem: "planejador" });
    });
    if (dec && dec.area_m2 > 0) out.push({ id: "app-declividade", nome: "APP de declividade (acima de 45°)", tipo: "app", area_m2: +dec.area_m2.toFixed(1), app: true, area_app_m2: +dec.area_m2.toFixed(1), objetivo: "restauracao_app", preservar: true, forma: "celulas", cs: dec.cs, celulas: dec.celulas, origem: "planejador" });
    return out;
  }
  const SOLO_PLANEJADOR = { areia: "arenoso", areia_argilosa: "arenoso", silte: "médio", argila_arenosa: "médio", argila: "argiloso", residual: "médio", coluvio: "médio" };
  function contextoTerreno(localStorageJson) {
    const S = lerJson(localStorageJson); if (!S) return null; const m = S.meta || {}, t = S.terreno || {}, i = S.inicio || {};
    return { nome: m.nome || "", municipio: m.municipio || "", uf: (m.uf || "").toUpperCase(), lat: t.lat0 != null ? t.lat0 : i.lat, lon: t.lon0 != null ? t.lon0 : i.lon,
      area_terreno_m2: Array.isArray(t.poly) && t.poly.length > 2 ? +areaPoly(t.poly).toFixed(1) : (num(i.area) || null),
      solo_textura: SOLO_PLANEJADOR[(S.solo || {}).classe] || "", temp_media_c: num((S.clima || {}).temp) };
  }

  /* ───────────── telas (HTML) ───────────── */
  const E = s => (typeof raiz.esc === "function" ? raiz.esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])));
  const N = (v, c) => (typeof raiz.n2 === "function" ? raiz.n2(v, c) : (v == null || !isFinite(v) ? "—" : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c || 0, maximumFractionDigits: c || 0 })));
  let seq = 0;
  /* ctx: { resultado } ou { opcoes, plantas }; opcional idBase */
  function telaSbnConsorcio(ctx) {
    ctx = ctx || {}; const r = ctx.resultado || montarConsorcio(ctx.opcoes || {}, ctx.plantas), id = ctx.idBase || ("sbn-c" + (++seq));
    const esp2 = e => e ? `${N(e[0], e[0] < 1 ? 2 : 1)} × ${N(e[1], e[1] < 1 ? 2 : 1)} m` : "—";
    const linhas = r.itens.map(i => `<tr><th scope="row">${E(i.nome)}<br><span class="t2 pq"><i>${E(i.cientifico)}</i>${i.nativa ? " · nativa" : ""}</span></th><td>${E(NOME_ESTRATO[i.estrato] || i.estrato || "—")}${i.zona ? " · " + E(i.zona) : ""}${i.grupo && r.objetivo === "restauracao_app" ? " · " + E(i.grupo) : ""}</td><td>${E(NOME_CICLO[i.ciclo] || i.ciclo || "—")}</td><td>${esp2(i.espacamento)}</td><td>${N(i.mudas, 0)} <span class="t2 pq">${E(i.unidade)}</span></td><td>${E(i.motivo)}</td></tr>`).join("");
    const est = Object.entries(r.estratos).map(([s, e]) => `<tr><th scope="row">${E(NOME_ESTRATO[s] || s)}</th><td>${e.especies}</td><td>${N(e.mudas, 0)}</td><td>${N(e.cobertura_pct, 1)}%</td><td>${e.min != null ? N(e.min, 0) + "–" + N(e.max, 0) + "%" : "—"}</td></tr>`).join("");
    const viol = r.violacoes.length ? `<ul>${r.violacoes.map(v => `<li><span class="selo ${v.nivel === "erro" ? "al" : "in"}">${v.nivel === "erro" ? "erro" : "aviso"}</span> ${E(v.texto)}</li>`).join("")}</ul>` : `<p class="t2">Nenhuma regra violada: sem invasoras, sem antagonistas, estratos e sucessão dentro dos limites.</p>`;
    return `<section class="cartao" aria-labelledby="${id}-h"><h2 id="${id}-h">${E(r.nome)} em ${N(r.area_m2, r.area_m2 < 100 ? 1 : 0)} m²${r.bioma ? " · " + E(r.bioma) : ""}</h2>
<ul class="t2">${r.explicacao.map(x => `<li>${E(x)}</li>`).join("")}</ul>
<div class="rolagem"><table><caption>Espécies do consórcio com estrato, sucessão, espaçamento e quantidade de mudas</caption><thead><tr><th scope="col">Planta</th><th scope="col">Estrato</th><th scope="col">Sucessão</th><th scope="col">Espaçamento</th><th scope="col">Quantidade</th><th scope="col">Por que entrou</th></tr></thead><tbody>${linhas || `<tr><td colspan="6">Nenhuma espécie.</td></tr>`}</tbody></table></div>
<p>Total: <strong>${N(r.total_mudas, 0)}</strong> mudas ou plantas · nativas: ${r.nativas_pct_especies}% das espécies e ${r.nativas_pct_mudas}% das mudas.</p>
${r.itens.length ? `<button type="button" data-sbn-cons-plano="${E(id)}">Levar ao plano de plantio</button>` : ""}</section>
<section class="cartao" aria-labelledby="${id}-he"><h2 id="${id}-he">Cobertura por estrato</h2><div class="rolagem"><table><caption>Cobertura das copas adultas por estrato, em porcentagem da área, com os limites usados</caption><thead><tr><th scope="col">Estrato</th><th scope="col">Espécies</th><th scope="col">Mudas</th><th scope="col">Cobertura</th><th scope="col">Limites</th></tr></thead><tbody>${est}</tbody></table></div></section>
<section class="cartao" aria-labelledby="${id}-hr"><h2 id="${id}-hr">Regras conferidas</h2>${viol}</section>`;
  }
  /* ctx: { terreno: json do localStorage (texto ou objeto) } */
  function telaSbnAreas(ctx) {
    ctx = ctx || {}; const id = ctx.idBase || ("sbn-a" + (++seq)), areas = ctx.areas || lerTerreno(ctx.terreno);
    const nomeObj = k => (OBJETIVOS[k] || {}).nome || "—";
    if (!areas.length) return `<section class="cartao" aria-labelledby="${id}-h"><h2 id="${id}-h">Áreas do Planejador</h2><p class="t2">Nenhuma área verde desenhada ainda. No Planejador, desenhe horta ou pomar, gramado ou jardim, mata preservada e valas ou jardins de infiltração; a declividade acima de 45° vira APP sozinha.</p></section>`;
    const linhas = areas.map(a => `<tr><th scope="row">${E(a.nome)}</th><td>${E((TIPOS_TERRENO[Object.keys(TIPOS_TERRENO).find(k => TIPOS_TERRENO[k].tipo === a.tipo)] || { nome: "APP" }).nome)}</td><td>${N(a.area_m2, 1)} m²</td><td>${a.app ? `<span class="selo al">APP</span> ${N(a.area_app_m2, 1)} m²` : "não"}</td><td>${E(nomeObj(a.objetivo))}</td><td>${a.objetivo ? `<button type="button" data-sbn-area="${E(a.id)}" data-sbn-obj="${E(a.objetivo)}" data-sbn-m2="${a.area_m2}" aria-label="Montar consórcio para ${E(a.nome)}">Montar consórcio</button>` : ""}</td></tr>`).join("");
    return `<section class="cartao" aria-labelledby="${id}-h"><h2 id="${id}-h">Áreas do Planejador</h2><p class="t2 pq">Lidas do projeto salvo no Planejador neste navegador. Área em APP (declividade acima de 45°, Lei 12.651/2012, art. 4º, V) recebe restauração com nativas.</p>
<div class="rolagem"><table><caption>Áreas verdes desenhadas no Planejador, com área, situação de APP e o consórcio sugerido</caption><thead><tr><th scope="col">Área</th><th scope="col">Tipo</th><th scope="col">Tamanho</th><th scope="col">APP</th><th scope="col">Sugestão</th><th scope="col"><span class="so-leitor">Ações</span></th></tr></thead><tbody>${linhas}</tbody></table></div></section>`;
  }

  /* ───────────── critérios a partir do GIS do lugar ─────────────
     gis: { zonas: ui.gisX.zonas (bioma IBGE, clima IBGE, vegetação original, Köppen), solo: ui.gisX.solo, lugar: {uf, lat, lon, altitude_m},
            biomaAprox: biomaDoLugar() (caixas, só se não houver o IBGE) }. Tudo é opcional. */
  function criteriosDoLugar(gis) {
    gis = gis || {}; const z = gis.zonas || {}, k = z.koppen || {}, cl = z.clima || {}, so = gis.solo || {}, L = gis.lugar || {};
    const c = { bioma: "", uf: (L.uf || "").toUpperCase(), solo: {}, clima: {}, notas: [], vegetacao: "" };
    const nb = z.bioma && (z.bioma.nom_bioma || z.bioma.nome);
    const bi = nb ? BIOMAS.find(b => semAcento(b) === semAcento(nb)) : null;
    if (bi) { c.bioma = bi; c.notas.push("Bioma pelos polígonos oficiais do IBGE: " + bi + "."); }
    else if (gis.biomaAprox) { c.bioma = gis.biomaAprox; c.notas.push("Bioma aproximado pelas coordenadas (sem os polígonos do IBGE): " + gis.biomaAprox + "."); }
    const ch = num(k.chuva_anual_mm); if (ch != null) c.clima.chuva_mm_ano = ch;
    let ms = num(k.meses_secos);
    if (ms == null && cl.distr_umid) { const m = String(cl.distr_umid).match(/(\d+)(?:\s*a\s*(\d+))?\s*mes/i); if (m) ms = +(m[2] || m[1]); else if (/super.?umido|sem seca/i.test(cl.distr_umid)) ms = 0; }
    if (ms != null) c.clima.meses_secos = ms;
    const tm = num(k.temp_media); if (tm != null) c.clima.temp_media_c = tm;
    const tf = num(k.temp_min_mensal);   /* média do mês mais frio */
    if (tf != null) {
      c.clima.tmin_c = Math.round((tf - 15) * 10) / 10;
      c.clima.geada = tf < 14;
      c.notas.push(`Frio estimado pela média do mês mais frio (${tf} °C): mínima absoluta ≈ ${c.clima.tmin_c} °C${c.clima.geada ? ", com risco de geada" : ", geada improvável"}. Confira com dados locais.`);
    } else if (/frio|mesotérmico brando/i.test(cl.temperatur || "")) { c.clima.geada = true; }
    const alt = num(L.altitude_m != null ? L.altitude_m : k.altitude_m); if (alt != null) c.altitude_m = alt;
    const tx = normTextura(so.textura || (so.pedologia && so.pedologia.textura)); if (tx) c.solo.textura = tx;
    const ph = num(so.ph); if (ph != null && ph < 5.5) c.solo.acido = true;
    const veg = z.vegetacao && (z.vegetacao.nm_pretet || z.vegetacao.legenda_1); if (veg) { c.vegetacao = String(veg); c.notas.push("Vegetação original (IBGE): " + veg + "."); }
    return c;
  }

  /* ───────────── unidades de conservação ───────────── */
  const UC_INTEGRAL = /^(parque|reserva biol|estac|esta[cç][aã]o ecol|monumento natural|ref[uú]gio de vida)/i;
  const UC_ART31_EXCECAO = /^([aá]rea de prote[cç][aã]o ambiental|floresta (nacional|estadual)|reserva extrativista|reserva de desenvolvimento)/i;
  const REGRAS_UC = [
    "Dentro de unidade de conservação é proibido introduzir espécies não autóctones (Lei 9.985/2000, art. 31), com exceções para APA, Floresta Nacional, Reserva Extrativista e Reserva de Desenvolvimento Sustentável.",
    "Na zona de amortecimento valem as normas do plano de manejo (Lei 9.985/2000, art. 25). Sem zona definida, o licenciamento perto da UC ouve o órgão gestor: 3 km para obras com EIA/RIMA e 2 km para as demais (Resolução CONAMA 428/2010).",
    "Na zona de amortecimento, plante nativas do bioma e evite exóticas, sobretudo as invasoras e as marcadas como possível invasora."
  ];
  function distKm(a, b) { const R = 6371, r = Math.PI / 180, dLa = (b.lat - a.lat) * r, dLo = (b.lon - a.lon) * r, x = Math.sin(dLa / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLo / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(x)); }
  /* lugar: { uf, regiao, bioma, lat, lon }. A base de UCs não tem coordenadas: sem elas, lista as da mesma UF (ou região). */
  function ucsDoLugar(lugar, baseArg) {
    lugar = lugar || {}; const b = baseArg || BASE, ucs = (b && !Array.isArray(b) && b.ucs) || [];
    const uf = String(lugar.uf || "").toUpperCase(), reg = lugar.regiao || regiaoDaUf(uf);
    let l = ucs.filter(u => (uf && (u.uf || []).includes(uf)) || (!uf && reg && u.regiao === reg));
    l = l.map(u => {
      const categoria = UC_INTEGRAL.test(u.nome) ? "proteção integral" : "uso sustentável";
      const d = (u.lat != null && u.lon != null && lugar.lat != null && lugar.lon != null) ? distKm(lugar, u) : null;
      return Object.assign({}, u, { categoria, aceita_exoticas_art31: UC_ART31_EXCECAO.test(u.nome), distancia_km: d != null ? +d.toFixed(1) : null, dentro_raio_3km: d != null ? d <= 3 : null, mesmo_bioma: lugar.bioma ? semAcento(u.bioma || "").includes(semAcento(lugar.bioma)) : null });
    }).sort((a, b) => (a.distancia_km == null ? 1e9 : a.distancia_km) - (b.distancia_km == null ? 1e9 : b.distancia_km) || (b.mesmo_bioma === true) - (a.mesmo_bioma === true) || a.nome.localeCompare(b.nome));
    return { ucs: l, regras: REGRAS_UC.slice(), criterio: uf ? "mesma UF (" + uf + ")" : reg ? "mesma região (" + reg + ")" : "sem localização", distancia_calculada: l.some(u => u.distancia_km != null) };
  }
  /* espécie indicada para zona de amortecimento de UC no bioma */
  function apropriadaZA(p, bioma) {
    if (!eEspecie(p)) return { apta: false, rotulo: "não é espécie" };
    if (p.invasora) return { apta: false, rotulo: "invasora: não plantar perto de UC" };
    if ((p.a_conferir || []).includes("invasora?")) return { apta: false, rotulo: "possível invasora (conferir)" };
    if (nativaDe(p, semBioma(bioma) ? "" : bioma)) return { apta: true, rotulo: "nativa" + (semBioma(bioma) ? "" : " do bioma") + ": indicada" };
    return { apta: false, rotulo: "exótica não invasora: só se o plano de manejo permitir" };
  }

  /* ───────────── mapa de plantio (GIS/BIM do Planejador + espaçamento) ───────────── */
  const CORES = ["#33512F", "#4B7547", "#7FA874", "#2F5E4E", "#8A9182", "#8A6A1F", "#C9A227", "#8A6410", "#5B4A7A", "#A85432", "#2F7D5B", "#B07A12"];
  const corDe = n => CORES[Math.abs(+n || 0) % CORES.length];
  const VERDES = ["horta", "gramado", "mata", "infiltracao"];
  /* estado do mapa: áreas desenhadas no Planejador + as ajustadas pelo usuário (salvoJson tem prioridade, por id) */
  function estadoMapa(terrenoJson, salvoJson) {
    const S = lerJson(terrenoJson) || {}, salvo = lerJson(salvoJson) || {}, T = S.terreno || {};
    const doPlan = lerTerreno(S).filter(a => a.forma === "ret").map(a => ({ id: a.id, nome: a.nome, forma: "ret", x: a.x, y: a.y, w: a.w, d: a.d, rot: a.rot, objetivo: a.objetivo || "agrofloresta", origem: "planejador", app: a.app }));
    const mapa = new Map(doPlan.map(a => [a.id, a]));
    (salvo.areas || []).forEach(a => mapa.set(a.id, Object.assign({}, mapa.get(a.id) || {}, a)));
    const app = lerTerreno(S).find(a => a.forma === "celulas");
    const construcoes = (S.itens || []).filter(i => i.tipo !== "acesso" && !VERDES.includes(i.tipo) && num(i.w) > 0 && num(i.d) > 0).map(i => ({ nome: i.nome || i.tipo, x: num(i.x) || 0, y: num(i.y) || 0, w: num(i.w), d: num(i.d), rot: num(i.rot) || 0 }));
    return { versao: 1, areas: [...mapa.values()].filter(a => !a.removida), sel: salvo.sel || null, poly: Array.isArray(T.poly) ? T.poly : [], construcoes, app: app ? { cs: app.cs, celulas: app.celulas } : null, lat0: T.lat0, lon0: T.lon0, grade: salvo.grade !== false };
  }
  function cantosRet(a) { const r = (num(a.rot) || 0) * Math.PI / 180, c = Math.cos(r), s = Math.sin(r); return [[-a.w / 2, -a.d / 2], [a.w / 2, -a.d / 2], [a.w / 2, a.d / 2], [-a.w / 2, a.d / 2]].map(([u, v]) => [a.x + u * c - v * s, a.y + u * s + v * c]); }
  function poligonoArea(a) { return a.forma === "poli" ? (a.pontos || []) : cantosRet(a); }
  function areaDaArea(a) { const P = poligonoArea(a); return P.length >= 3 ? areaPoly(P) : 0; }
  function lerPontos(txt) { return String(txt || "").split(/;|\n/).map(t => t.trim().split(/[\s,]+/).map(Number)).filter(p => p.length >= 2 && isFinite(p[0]) && isFinite(p[1])).map(p => [p[0], p[1]]); }
  /* posições das plantas na área, no espaçamento real de cada estrato.
     Agrofloresta/horta/pomar/jardim: cada estrato tem sua grade (área por planta = área ÷ mudas do estrato, na proporção
     entre plantas × entre linhas da espécie principal), em quincôncio e deslocada dos outros estratos.
     Restauração: grade 3 × 2 m com linhas alternadas de preenchimento e diversidade. */
  function gradePlantio(area, res, limite) {
    limite = limite || 4000; const out = { pontos: [], planejadas: 0, desenhadas: 0, escala: 1, avisos: [] };
    if (!area || !res || !res.itens || !res.itens.length) return out;
    const P = poligonoArea(area); if (P.length < 3) return out;
    let fr, U, V, u0, v0;   /* referencial: retângulo girado (u ao longo da largura) ou caixa do polígono */
    if (area.forma !== "poli") { const r = (num(area.rot) || 0) * Math.PI / 180, c = Math.cos(r), s = Math.sin(r); fr = (u, v) => [area.x + u * c - v * s, area.y + u * s + v * c]; U = area.w; V = area.d; u0 = -U / 2; v0 = -V / 2; }
    else { const xs = P.map(p => p[0]), ys = P.map(p => p[1]); u0 = Math.min(...xs); v0 = Math.min(...ys); U = Math.max(...xs) - u0; V = Math.max(...ys) - v0; fr = (u, v) => [u, v]; }
    const dentro = pt => dentroPoly(pt, P), A = areaPoly(P);
    const total = res.itens.reduce((t, i) => t + i.mudas, 0); out.planejadas = total;
    const esc = total > limite ? limite / total : 1; out.escala = esc;
    if (esc < 1) out.avisos.push(`Desenho em escala: cada ponto vale ${(1 / esc).toFixed(1).replace(".", ",")} plantas.`);
    /* sequência equilibrada das espécies: a cada posição, a que está mais atrás da sua cota */
    const sequencia = (itens, n) => { const tot = itens.reduce((t, i) => t + i.mudas, 0) || 1, feitos = itens.map(() => 0), seq = []; for (let k = 0; k < n; k++) { let b = 0, bv = -Infinity; itens.forEach((it, j) => { const v = it.mudas / tot * (k + 1) - feitos[j]; if (v > bv) { bv = v; b = j; } }); feitos[b]++; seq.push(itens[b]); } return seq; };
    const grade = (a, b, fase, cb) => { const nl = Math.max(1, Math.floor(V / b + 1e-9)), np = Math.max(1, Math.floor(U / a + 1e-9)); for (let l = 0; l < nl; l++) { const v = v0 + b / 2 + l * b; for (let j = 0; j < np; j++) { const u = u0 + a / 2 + j * a + ((l % 2) ? a / 2 : 0) * (np > 1 ? 1 : 0) + fase * a; if (u > u0 + U) continue; const pt = fr(u, v); if (dentro(pt)) cb(pt, l); } } };
    if (res.objetivo === "restauracao_app") {
      const [el, ep] = res.grade_m || GRADE_RESTAURACAO, pts = [];
      grade(ep, el, 0, (pt, l) => pts.push([pt, l]));
      const grupos = { preenchimento: res.itens.filter(i => i.grupo === "preenchimento"), diversidade: res.itens.filter(i => i.grupo === "diversidade") };
      const nPorLinha = { 0: pts.filter(p => p[1] % 2 === 0).length, 1: pts.filter(p => p[1] % 2 === 1).length };
      const seqs = { 0: sequencia(grupos.preenchimento.length ? grupos.preenchimento : grupos.diversidade, nPorLinha[0]), 1: sequencia(grupos.diversidade.length ? grupos.diversidade : grupos.preenchimento, nPorLinha[1]) };
      const pos = { 0: 0, 1: 0 };
      pts.forEach(([pt, l]) => { const g = l % 2, it = seqs[g][pos[g]++]; if (it) out.pontos.push({ x: pt[0], y: pt[1], n: it.n, nome: it.nome, estrato: it.estrato, r: 0.9 }); });
      if (Math.abs(pts.length - total) > Math.max(2, total * 0.1)) out.avisos.push(`A forma da área comporta ${pts.length} covas na grade de ${el} × ${ep} m; o plano tem ${total} mudas.`);
    } else {
      const est = {}; res.itens.forEach(i => (est[i.estrato] = est[i.estrato] || []).push(i));
      Object.keys(est).forEach((s, idx) => {
        const itens = est[s], m = Math.max(1, Math.round(itens.reduce((t, i) => t + i.mudas, 0) * esc));
        const e0 = itens[0].espacamento || [1, 1], cel = A / m, a = Math.sqrt(cel * e0[0] / e0[1]), b = cel / a;
        const pts = []; grade(a, b, (idx * 0.37) % 1, pt => pts.push(pt));
        const seq = sequencia(itens, Math.min(m, pts.length));
        const raio = { emergente: 0.45, alto: 0.4, medio: 0.35, baixo: 0.3, rasteiro: 0.22, trepadeira: 0.25, aquatica: 0.3 }[s] || 0.3;
        seq.forEach((it, k) => out.pontos.push({ x: pts[k][0], y: pts[k][1], n: it.n, nome: it.nome, estrato: s, r: Math.min(Math.min(a, b) * raio, Math.sqrt(e0[0] * e0[1]) / 2), a, b }));
        if (pts.length < m * 0.9) out.avisos.push(`Estrato ${(NOME_ESTRATO[s] || s).toLowerCase()}: a forma da área comporta ${pts.length} de ${m} posições.`);
      });
    }
    out.desenhadas = out.pontos.length;
    return out;
  }
  /* ctx: { estado (de estadoMapa), consorcios: { [idArea]: resultado de montarConsorcio }, idBase, largura } */
  function telaSbnMapa(ctx) {
    ctx = ctx || {}; const st = ctx.estado || estadoMapa(ctx.terreno, ctx.salvo), id = ctx.idBase || "sbn-m", cons = ctx.consorcios || {};
    const todos = [].concat(st.poly || [], ...st.areas.map(poligonoArea), ...st.construcoes.map(cantosRet));
    const semDesenho = !todos.length;
    const xs = semDesenho ? [0, 20] : todos.map(p => p[0]), ys = semDesenho ? [0, 20] : todos.map(p => p[1]);
    const mx = Math.max(2, (Math.max(...xs) - Math.min(...xs)) * 0.04), x0 = Math.min(...xs) - mx, x1 = Math.max(...xs) + mx, y0 = Math.min(...ys) - mx, y1 = Math.max(...ys) + mx;
    const W = x1 - x0, H = y1 - y0, X = x => (x - x0).toFixed(2), Y = y => (y1 - y).toFixed(2);   /* norte para cima */
    const pts = P => P.map(p => X(p[0]) + "," + Y(p[1])).join(" ");
    const lw = Math.max(W, H) / 400;
    let svg = "";
    if (st.poly && st.poly.length > 2) svg += `<polygon points="${pts(st.poly)}" fill="#EEF2EA" stroke="#1C2B21" stroke-width="${(lw * 2).toFixed(2)}"/>`;
    if (st.app && st.app.celulas) svg += st.app.celulas.map(c => `<rect x="${X(c[0] - st.app.cs / 2)}" y="${Y(c[1] + st.app.cs / 2)}" width="${st.app.cs.toFixed(2)}" height="${st.app.cs.toFixed(2)}" fill="#C2410C" fill-opacity="0.25"/>`).join("");
    svg += st.construcoes.map(c => `<polygon points="${pts(cantosRet(c))}" fill="#8A9284" fill-opacity="0.7"><title>${E(c.nome)} (construção)</title></polygon>`).join("");
    const legenda = new Map(); let nPontos = 0, avisos = [];
    st.areas.forEach(a => {
      const sel = st.sel === a.id, P = poligonoArea(a); if (P.length < 3) return;
      svg += `<polygon points="${pts(P)}" fill="${a.app ? "#E3C4BD" : "#CDDCC4"}" fill-opacity="0.55" stroke="${sel ? "#C9A227" : "#33512F"}" stroke-width="${(lw * (sel ? 4 : 2)).toFixed(2)}" tabindex="0" role="button" focusable="true" data-sbn-m-area="${E(a.id)}" aria-label="${E(a.nome)}: ${N(areaDaArea(a), 1)} m². Setas movem 0,5 m; Shift+setas mudam o tamanho; R gira 5 graus" style="cursor:move"><title>${E(a.nome)}</title></polygon>`;
      const r = cons[a.id];
      if (r && st.grade !== false) {
        const g = gradePlantio(a, r); avisos = avisos.concat(g.avisos.map(t => a.nome + ": " + t)); nPontos += g.desenhadas;
        svg += g.pontos.map(p => `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="${Math.max(lw * 1.5, p.r).toFixed(2)}" fill="${corDe(p.n)}" fill-opacity="0.85" pointer-events="none"/>`).join("");
        r.itens.forEach(i => legenda.set(i.n, i));
      }
    });
    const opts = (v) => Object.keys(OBJETIVOS).map(k => `<option value="${k}" ${v === k ? "selected" : ""}>${E(OBJETIVOS[k].nome)}</option>`).join("");
    const campo = (a, k, rot, v, passo) => `<label>${rot}<br><input type="number" step="${passo || 0.5}" data-sbn-m-id="${E(a.id)}" data-sbn-m-k="${k}" value="${v != null ? +(+v).toFixed(2) : ""}" style="width:6em"></label>`;
    const linhas = st.areas.map(a => `<fieldset data-sbn-m-linha="${E(a.id)}"${st.sel === a.id ? ' aria-current="true"' : ""}><legend>${E(a.nome)} · ${N(areaDaArea(a), 1)} m²${a.app ? " · APP" : ""}${a.origem === "planejador" ? " · do Planejador" : ""}</legend>
<label>Nome<br><input type="text" data-sbn-m-id="${E(a.id)}" data-sbn-m-k="nome" value="${E(a.nome)}"></label>
<label>Consórcio<br><select data-sbn-m-id="${E(a.id)}" data-sbn-m-k="objetivo">${opts(a.objetivo)}</select></label>
${a.forma === "poli" ? `<label>Pontos (x y; x y; …, em metros)<br><textarea rows="2" cols="34" data-sbn-m-id="${E(a.id)}" data-sbn-m-k="pontos">${E((a.pontos || []).map(p => p[0] + " " + p[1]).join("; "))}</textarea></label>`
  : campo(a, "x", "Centro x (m)", a.x) + campo(a, "y", "Centro y (m)", a.y) + campo(a, "w", "Largura (m)", a.w) + campo(a, "d", "Profundidade (m)", a.d) + campo(a, "rot", "Giro (graus)", a.rot, 5)}
<button type="button" data-sbn-m-acao="selecionar" data-sbn-m-id="${E(a.id)}">Selecionar</button> <button type="button" data-sbn-m-acao="consorcio" data-sbn-m-id="${E(a.id)}">Montar consórcio aqui</button> <button type="button" data-sbn-m-acao="remover" data-sbn-m-id="${E(a.id)}" aria-label="Remover ${E(a.nome)}">Remover</button></fieldset>`).join("");
    const leg = [...legenda.values()].map(i => `<li><span aria-hidden="true" style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${corDe(i.n)}"></span> ${E(i.nome)} (${E(NOME_ESTRATO[i.estrato] || i.estrato)}, ${N(i.mudas, 0)})</li>`).join("");
    return `<section class="cartao" aria-labelledby="${id}-h" data-sbn-mapa="${E(id)}"><h2 id="${id}-h">Mapa de plantio e espaçamento</h2>
<p class="t2 pq">Desenho do terreno e das áreas do Planejador (norte para cima, em metros). Arraste uma área para mover ou use o teclado: Tab até a área, setas movem 0,5 m, Shift+setas mudam o tamanho, R gira 5°. Os pontos são as plantas no espaçamento real de cada estrato; em vermelho, a APP de declividade; em cinza, as construções.</p>
<svg viewBox="0 0 ${W.toFixed(2)} ${H.toFixed(2)}" width="100%" style="max-width:${ctx.largura || 720}px;background:#F7F8F4;border-radius:8px;touch-action:none" role="group" aria-label="Planta do terreno com ${st.areas.length} áreas de plantio e ${nPontos} plantas desenhadas" data-sbn-m-svg="1">${svg}</svg>
${semDesenho ? `<p class="t2">Sem desenho do Planejador neste navegador. Crie uma área abaixo (retângulo ou pontos).</p>` : ""}
${leg ? `<ul style="list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:4px 14px">${leg}</ul>` : ""}
${avisos.length ? `<ul class="t2 pq">${avisos.map(t => `<li>${E(t)}</li>`).join("")}</ul>` : ""}
<div data-sbn-m-gis="1" style="display:none;height:320px;border-radius:8px"></div>
<p><button type="button" data-sbn-m-acao="nova-ret">Nova área retangular</button> <button type="button" data-sbn-m-acao="nova-poli">Nova área por pontos</button> <label><input type="checkbox" data-sbn-m-k="grade" ${st.grade !== false ? "checked" : ""}> Mostrar a grade de plantio</label></p>
${linhas}</section>`;
  }
  /* liga o mapa num elemento da página (uma vez): ctx = { estado, consorcios, idBase }; aoMudar(estado, acao, idArea) é chamado
     a cada mudança (o painel grava e, na ação "consorcio", monta o consórcio da área). Redesenha sozinho. */
  function ligarMapa(el, ctx, aoMudar) {
    if (!el || !ctx || !ctx.estado) return;
    ctx.__cb = aoMudar || (() => {});
    const C = () => el.__sbnMapa;
    const redesenhar = (foco) => { el.innerHTML = telaSbnMapa(C()); if (foco) { const f = el.querySelector(foco); if (f) f.focus(); } };
    const area = id => C().estado.areas.find(a => a.id === id);
    const mudou = (acao, id, foco) => { redesenhar(foco); try { C().__cb(C().estado, acao, id); } catch (e) {} };
    if (el.__sbnMapa) { el.__sbnMapa = ctx; redesenhar(); return; }
    el.__sbnMapa = ctx;
    el.addEventListener("change", ev => {
      const t = ev.target, k = t.dataset && t.dataset.sbnMK; if (!k) return; const c = C();
      if (k === "grade") { c.estado.grade = t.checked; return mudou("grade"); }
      const a = c.estado.areas.find(x => x.id === t.dataset.sbnMId); if (!a) return;
      if (k === "pontos") a.pontos = lerPontos(t.value); else if (k === "nome" || k === "objetivo") a[k] = t.value; else { const v = num(t.value); if (v == null) return; a[k] = (k === "w" || k === "d") ? Math.max(0.5, v) : v; }
      mudou("editar", a.id, `[data-sbn-m-id="${a.id}"][data-sbn-m-k="${k}"]`);
    });
    el.addEventListener("click", ev => {
      const b = ev.target.closest && ev.target.closest("[data-sbn-m-acao]"); if (!b) return; const c = C(), ac = b.dataset.sbnMAcao, id = b.dataset.sbnMId;
      if (ac === "nova-ret" || ac === "nova-poli") {
        const P = c.estado.poly && c.estado.poly.length ? c.estado.poly : [[0, 0], [20, 20]], xs = P.map(p => p[0]), ys = P.map(p => p[1]), cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const nid = "sbn-" + Date.now().toString(36), n = c.estado.areas.length + 1;
        c.estado.areas.push(ac === "nova-ret" ? { id: nid, nome: "Área " + n, forma: "ret", x: +cx.toFixed(1), y: +cy.toFixed(1), w: 10, d: 6, rot: 0, objetivo: "agrofloresta", origem: "usuario" }
          : { id: nid, nome: "Área " + n, forma: "poli", pontos: [[cx - 5, cy - 3], [cx + 5, cy - 3], [cx + 4, cy + 4], [cx - 5, cy + 3]].map(p => [+p[0].toFixed(1), +p[1].toFixed(1)]), objetivo: "agrofloresta", origem: "usuario" });
        c.estado.sel = nid; return mudou("nova", nid, `[data-sbn-m-id="${nid}"][data-sbn-m-k="nome"]`);
      }
      if (ac === "remover") { c.estado.areas = c.estado.areas.filter(a => a.id !== id); delete (c.consorcios || {})[id]; return mudou("remover", id); }
      if (ac === "selecionar") { c.estado.sel = id; return mudou("selecionar", id, `[data-sbn-m-area="${id}"]`); }
      if (ac === "consorcio") { c.estado.sel = id; return mudou("consorcio", id); }
    });
    el.addEventListener("keydown", ev => {
      const t = ev.target, id = t.dataset && t.dataset.sbnMArea; if (!id) return; const a = area(id); if (!a) return;
      const passo = 0.5, dx = { ArrowLeft: -1, ArrowRight: 1 }[ev.key] || 0, dy = { ArrowUp: 1, ArrowDown: -1 }[ev.key] || 0;
      if (dx || dy) {
        ev.preventDefault();
        if (ev.shiftKey && a.forma !== "poli") { a.w = Math.max(0.5, a.w + dx * passo); a.d = Math.max(0.5, a.d + dy * passo); }
        else if (a.forma === "poli") a.pontos = a.pontos.map(p => [p[0] + dx * passo, p[1] + dy * passo]);
        else { a.x += dx * passo; a.y += dy * passo; }
      } else if ((ev.key === "r" || ev.key === "R") && a.forma !== "poli") { a.rot = ((num(a.rot) || 0) + (ev.shiftKey ? -5 : 5)) % 360; }
      else if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); C().estado.sel = id; }
      else return;
      mudou("editar", id, `[data-sbn-m-area="${id}"]`);
    });
    let arr = null;
    const ptSvg = (svg, ev) => { const m = svg.getScreenCTM(); if (!m) return null; const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; const q = p.matrixTransform(m.inverse()); return [q.x, q.y]; };
    el.addEventListener("pointerdown", ev => { const t = ev.target, id = t.dataset && t.dataset.sbnMArea; if (!id) return; const svg = t.ownerSVGElement, p0 = ptSvg(svg, ev); if (!p0) return; arr = { id, svg, p0, t }; try { t.setPointerCapture(ev.pointerId); } catch (e) {} ev.preventDefault(); });
    el.addEventListener("pointermove", ev => { if (!arr) return; const p = ptSvg(arr.svg, ev); if (!p) return; arr.t.setAttribute("transform", `translate(${p[0] - arr.p0[0]} ${p[1] - arr.p0[1]})`); arr.d = [p[0] - arr.p0[0], -(p[1] - arr.p0[1])]; });
    el.addEventListener("pointerup", () => { if (!arr) return; const a = area(arr.id), d = arr.d; const id = arr.id; arr = null; if (!a) return; C().estado.sel = id;
      if (d && (Math.abs(d[0]) > 0.05 || Math.abs(d[1]) > 0.05)) { if (a.forma === "poli") a.pontos = a.pontos.map(p => [+(p[0] + d[0]).toFixed(2), +(p[1] + d[1]).toFixed(2)]); else { a.x = +(a.x + d[0]).toFixed(2); a.y = +(a.y + d[1]).toFixed(2); } }
      mudou("editar", id, `[data-sbn-m-area="${id}"]`); });
    redesenhar();
  }
  /* mapa GIS (MapLibre) sem fundo externo: só os desenhos em coordenadas reais. Precisa de window.maplibregl e de lat0/lon0;
     assume que o Planejador guarda metros locais (x leste, y norte) a partir de lat0/lon0. */
  function abrirMapaGis(container, ctx) {
    const ml = raiz.maplibregl, st = ctx && ctx.estado; if (!ml || !container || !st || st.lat0 == null || st.lon0 == null) return null;
    const la0 = +st.lat0, lo0 = +st.lon0, ll = p => [lo0 + p[0] / (111320 * Math.cos(la0 * Math.PI / 180)), la0 + p[1] / 110540];
    const anel = P => { const r = P.map(ll); r.push(r[0]); return [r]; };
    const F = [];
    if (st.poly && st.poly.length > 2) F.push({ type: "Feature", properties: { tipo: "terreno" }, geometry: { type: "Polygon", coordinates: anel(st.poly) } });
    st.construcoes.forEach(c => F.push({ type: "Feature", properties: { tipo: "construcao" }, geometry: { type: "Polygon", coordinates: anel(cantosRet(c)) } }));
    st.areas.forEach(a => { const P = poligonoArea(a); if (P.length > 2) F.push({ type: "Feature", properties: { tipo: a.app ? "app" : "area", nome: a.nome }, geometry: { type: "Polygon", coordinates: anel(P) } }); });
    const G = []; Object.entries((ctx.consorcios) || {}).forEach(([id, r]) => { const a = st.areas.find(x => x.id === id); if (a) gradePlantio(a, r).pontos.forEach(p => G.push({ type: "Feature", properties: { cor: corDe(p.n), nome: p.nome }, geometry: { type: "Point", coordinates: ll([p.x, p.y]) } })); });
    const todos = F.flatMap(f => f.geometry.coordinates[0]); if (!todos.length) return null;
    container.style.display = "block";
    const lons = todos.map(c => c[0]), lats = todos.map(c => c[1]);
    const mapa = new ml.Map({ container, attributionControl: false, bounds: [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], fitBoundsOptions: { padding: 20 },
      style: { version: 8, sources: { d: { type: "geojson", data: { type: "FeatureCollection", features: F } }, g: { type: "geojson", data: { type: "FeatureCollection", features: G } } },
        layers: [{ id: "fundo", type: "background", paint: { "background-color": "#F7F8F4" } },
          { id: "terreno", type: "fill", source: "d", filter: ["==", ["get", "tipo"], "terreno"], paint: { "fill-color": "#EEF2EA", "fill-outline-color": "#1C2B21" } },
          { id: "construcoes", type: "fill", source: "d", filter: ["==", ["get", "tipo"], "construcao"], paint: { "fill-color": "#8A9284" } },
          { id: "areas", type: "fill", source: "d", filter: ["in", ["get", "tipo"], ["literal", ["area", "app"]]], paint: { "fill-color": ["match", ["get", "tipo"], "app", "#E3C4BD", "#CDDCC4"], "fill-opacity": 0.6, "fill-outline-color": "#33512F" } },
          { id: "plantas", type: "circle", source: "g", paint: { "circle-color": ["get", "cor"], "circle-radius": 3 } }] } });
    return mapa;
  }

  /* ctx: { uf, regiao, bioma, lat, lon, plantas } → unidades de conservação do lugar, regras da zona de amortecimento e espécies indicadas */
  function telaSbnUcs(ctx) {
    ctx = ctx || {}; const id = ctx.idBase || ("sbn-u" + (++seq)), r = ucsDoLugar(ctx), ps = plantasDe(ctx.plantas).filter(eEspecie);
    const aptas = ps.filter(p => apropriadaZA(p, ctx.bioma).apta);
    const linhas = r.ucs.map(u => `<tr><th scope="row">${E(u.nome)}</th><td>${E(u.categoria)}</td><td>${E(u.bioma || "—")}</td><td>${E((u.uf || []).join(", "))}</td><td>${u.distancia_km != null ? N(u.distancia_km, 1) + " km" : "—"}</td></tr>`).join("");
    return `<section class="cartao" aria-labelledby="${id}-h"><h2 id="${id}-h">Unidades de conservação e zona de amortecimento</h2>
${r.ucs.length ? `<div class="rolagem"><table><caption>Unidades de conservação da base no critério: ${E(r.criterio)}${r.distancia_calculada ? "" : " (a base não tem coordenadas: distância não calculada)"}</caption><thead><tr><th scope="col">Unidade</th><th scope="col">Categoria</th><th scope="col">Bioma</th><th scope="col">UF</th><th scope="col">Distância</th></tr></thead><tbody>${linhas}</tbody></table></div>` : `<p class="t2">Nenhuma unidade de conservação da base para ${E(r.criterio)}.</p>`}
<ul class="t2">${r.regras.map(t => `<li>${E(t)}</li>`).join("")}</ul>
<p class="t2">${aptas.length} espécies da base são indicadas para zona de amortecimento${semBioma(ctx.bioma) ? "" : " no bioma " + E(ctx.bioma)} (nativas e sem suspeita de invasão). Use o filtro "zona de amortecimento" para ver só elas.</p></section>`;
  }

  /* ───────────── conferência (item de planejamento) ─────────────
     Lista o que um especialista precisa conferir no plano atual: espécies com dados incertos, regras dos consórcios
     e lacunas de dados do lugar. A situação de cada item fica em localStorage "physis-sbn", chave "conferencia". */
  const CHAVE_SBN = "physis-sbn";
  const SITUACOES_CONFERENCIA = ["a conferir", "conferido", "ajustado"];
  const ROTULO_CONFERIR = {
    "nativa_de?": "biomas de origem (nativa_de)", "nativa_br?": "se é nativa do Brasil", "invasora?": "se é invasora (Instituto Hórus)",
    "altitude_m?": "faixa de altitude", "biomas?": "biomas onde ocorre", "funcoes?": "funções (por exemplo, se fixa nitrogênio)",
    "cientifico?": "nome científico (Flora e Funga do Brasil)", "restauracao_app?": "se serve para APP", "ciclo?": "fase da sucessão",
    "solo.umido?": "tolerância a solo encharcado", "solo.seco?": "tolerância à seca", "estrato?": "estrato"
  };
  const rotuloConferir = k => ROTULO_CONFERIR[k] || String(k).replace(/\?$/, "");
  function hashTxt(t) { let h = 0; for (const c of String(t)) h = (h * 31 + c.charCodeAt(0)) | 0; return (h >>> 0).toString(36); }
  /* ctx: { plano: [{n, qtd, espaco}] (o plano de plantio do painel), consorcios: [resultado…] ou {id: resultado},
            lugar: critérios do lugar (bioma, solo, clima, altitude_m), plantas } */
  function itensConferencia(ctx) {
    ctx = ctx || {}; const P = new Map(plantasDe(ctx.plantas).map(p => [p.n, p])), out = [], vistos = new Set();
    const cons = Array.isArray(ctx.consorcios) ? ctx.consorcios : Object.values(ctx.consorcios || {});
    const ns = new Set([...(ctx.plano || []).map(x => +x.n), ...cons.flatMap(r => (r.itens || []).map(i => i.n))].filter(n => n > 0));
    const add = (id, tipo, titulo, detalhe, extra) => { if (vistos.has(id)) return; vistos.add(id); out.push(Object.assign({ id, tipo, titulo, detalhe }, extra || {})); };
    [...ns].sort((a, b) => a - b).forEach(n => {
      const p = P.get(n); if (!p) return add("esp:" + n, "especie", "Planta nº " + n, "Não existe na base: conferir o plano.");
      const nome = `${p.nome} (${p.cientifico})`;
      (p.a_conferir || []).forEach(k => add(`esp:${n}:${k}`, "especie", nome, "Conferir " + rotuloConferir(k) + ".", { n }));
      if (p.invasora) add(`esp:${n}:invasora`, "especie", nome, "Marcada como invasora: confirmar se pode ficar no plano (e nunca perto de UC ou APP).", { n });
      const e = p.espacamento;
      if (!e) add(`esp:${n}:espacamento`, "especie", nome, "Sem espaçamento na base.", { n });
      else if (e.confianca === "baixa") add(`esp:${n}:espacamento`, "especie", nome, `Espaçamento ${e.entre_plantas_m} × ${e.entre_linhas_m} m com confiança baixa (${e.fonte}).`, { n });
      if (p.clima && p.clima.confianca === "baixa" && ctx.lugar && ctx.lugar.clima && Object.keys(ctx.lugar.clima).length) add(`esp:${n}:clima`, "especie", nome, `Faixas de clima do perfil "${p.clima.perfil}" (não da espécie): conferir frio, chuva e meses secos para o lugar.`, { n });
      if (/perfil/.test(p.altitude_fonte || "") && ctx.lugar && ctx.lugar.altitude_m != null) add(`esp:${n}:altitude`, "especie", nome, `Altitude ${p.altitude_m.join("–")} m vem do perfil climático, não de levantamento da espécie.`, { n });
    });
    cons.forEach(r => (r.violacoes || []).forEach(v => add(`regra:${r.objetivo}:${v.regra}:${hashTxt(v.texto)}`, "regra", `${OBJETIVOS[r.objetivo] ? OBJETIVOS[r.objetivo].nome : r.objetivo} (${N(r.area_m2, 0)} m²)`, `${v.nivel === "erro" ? "Erro" : "Aviso"}: ${v.texto}`, { nivel: v.nivel })));
    const L = ctx.lugar || {}, cl = L.clima || {}, so = L.solo || {};
    if (semBioma(L.bioma)) add("lugar:bioma", "lugar", "Lugar", "Bioma desconhecido: informe a localização (polígonos do IBGE) ou escolha o bioma.");
    if (!so.textura) add("lugar:textura", "lugar", "Lugar", "Textura do solo desconhecida: base de solos do GIS ou análise de solo.");
    if (cl.chuva_mm_ano == null) add("lugar:chuva", "lugar", "Lugar", "Chuva anual desconhecida.");
    if (cl.meses_secos == null) add("lugar:meses_secos", "lugar", "Lugar", "Número de meses secos desconhecido.");
    if (cl.tmin_c == null && cl.geada == null) add("lugar:frio", "lugar", "Lugar", "Frio e geada desconhecidos (média do mês mais frio ou registro local).");
    if (L.altitude_m == null) add("lugar:altitude", "lugar", "Lugar", "Altitude desconhecida.");
    return out;
  }
  function conferenciaCsv(itens, estado) {
    estado = estado || {}; const q = v => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
    return ["Tipo;Item;O que conferir;Situação;Responsável;Data;Observação"].concat(itens.map(i => { const s = estado[i.id] || {}; return [i.tipo, i.titulo, i.detalhe, s.situacao || "a conferir", s.responsavel, s.data, s.obs].map(q).join(";"); })).join("\r\n");
  }
  /* ctx: os de itensConferencia + estado (mapa id → {situacao, responsavel, data, obs}); sem estado, lê localStorage na hora */
  function lerEstadoConferencia() { try { return (JSON.parse(raiz.localStorage.getItem(CHAVE_SBN) || "{}").conferencia) || {}; } catch (e) { return {}; } }
  function telaSbnConferencia(ctx) {
    ctx = ctx || {}; const id = ctx.idBase || ("sbn-f" + (++seq)), itens = ctx.itens || itensConferencia(ctx), est = ctx.estado || lerEstadoConferencia();
    const sit = i => (est[i.id] || {}).situacao || "a conferir";
    const cont = SITUACOES_CONFERENCIA.map(s => `${itens.filter(i => sit(i) === s).length} ${s}`).join(" · ");
    const NT = { especie: "Espécie", regra: "Regra", lugar: "Lugar" };
    const linhas = itens.map((i, k) => { const s = est[i.id] || {}, a = `data-sbn-conf-id="${E(i.id)}"`, rid = `${id}-${k}`;
      return `<tr><th scope="row">${E(NT[i.tipo] || i.tipo)}: ${E(i.titulo)}</th><td>${E(i.detalhe)}</td>
<td><label class="so-leitor" for="${rid}-s">Situação</label><select id="${rid}-s" ${a} data-sbn-conf-k="situacao">${SITUACOES_CONFERENCIA.map(x => `<option ${sit(i) === x ? "selected" : ""}>${x}</option>`).join("")}</select></td>
<td><label class="so-leitor" for="${rid}-r">Responsável</label><input id="${rid}-r" type="text" ${a} data-sbn-conf-k="responsavel" value="${E(s.responsavel || "")}" style="width:9em"></td>
<td><label class="so-leitor" for="${rid}-d">Data</label><input id="${rid}-d" type="date" ${a} data-sbn-conf-k="data" value="${E(s.data || "")}"></td>
<td><label class="so-leitor" for="${rid}-o">Observação</label><input id="${rid}-o" type="text" ${a} data-sbn-conf-k="obs" value="${E(s.obs || "")}" style="width:100%"></td></tr>`; }).join("");
    return `<section class="cartao" aria-labelledby="${id}-h" data-sbn-conferencia="${E(id)}"><h2 id="${id}-h">Conferência</h2>
<p class="t2">O que um especialista precisa conferir antes de levar o plano a laudo ou ao cliente: espécies com dados incertos, regras dos consórcios e dados que faltam do lugar. ${itens.length ? cont + "." : ""}</p>
${itens.length ? `<div class="rolagem"><table><caption>Itens a conferir, com situação, responsável, data e observação</caption><thead><tr><th scope="col">Item</th><th scope="col">O que conferir</th><th scope="col">Situação</th><th scope="col">Responsável</th><th scope="col">Data</th><th scope="col">Observação</th></tr></thead><tbody>${linhas}</tbody></table></div>
<p><button type="button" data-sbn-conf-exportar="1">Exportar a tabela (CSV)</button> <button type="button" data-sbn-conf-exportar="xlsx">Exportar a tabela (Excel)</button></p>` : `<p class="t2">Nada a conferir no plano atual.</p>`}</section>`;
  }
  /* liga a tabela (uma vez por elemento): grava cada mudança em localStorage "physis-sbn".conferencia
     (ou em ctx.gravar(estado), se vier) e exporta o CSV; aoMudar(estado, idItem) é opcional */
  function ligarConferencia(el, ctx, aoMudar) {
    if (!el) return; ctx = ctx || {}; el.__sbnConf = ctx;
    const C = () => el.__sbnConf;
    const estado = () => C().estado || (C().estado = lerEstadoConferencia());
    const gravar = est => { if (C().gravar) return C().gravar(est); try { const o = JSON.parse(raiz.localStorage.getItem(CHAVE_SBN) || "{}"); o.conferencia = est; raiz.localStorage.setItem(CHAVE_SBN, JSON.stringify(o)); } catch (e) {} };
    if (el.__sbnConfLigado) return; el.__sbnConfLigado = true;
    const mudar = ev => { const t = ev.target, k = t.dataset && t.dataset.sbnConfK, i = t.dataset && t.dataset.sbnConfId; if (!k || !i) return;
      const est = estado(); est[i] = Object.assign({ situacao: "a conferir" }, est[i] || {}, { [k]: t.value }); gravar(est); if (aoMudar) try { aoMudar(est, i); } catch (e) {} };
    el.addEventListener("change", mudar);
    el.addEventListener("click", ev => { const b = ev.target.closest && ev.target.closest("[data-sbn-conf-exportar]"); if (!b) return;
      const c = C(), csv = "﻿" + conferenciaCsv(c.itens || itensConferencia(c), estado());
      const PE = raiz.PhysisExportar;   // Excel editável com o mesmo conteúdo (physis-exportar.js), quando a tela tem a biblioteca
      if (b.dataset.sbnConfExportar === "xlsx" && PE && PE.csvParaXlsx) { try { PE.baixar("conferencia-sbn.xlsx", PE.csvParaXlsx("Conferência do plano SbN", csv), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); } catch (e) {} return; }
      try { const a = raiz.document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); a.download = "conferencia-sbn.csv"; raiz.document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0); } catch (e) {} });
  }

  const api = { versao: VERSAO, BIOMAS, ESTRATOS_SAF, CICLOS, COBERTURA, OBJETIVOS, GRADE_RESTAURACAO, NATIVAS_MIN_APP,
    carregar, avaliar, filtrar, montarConsorcio, verificar, mudas, mudasInfo, lerTerreno, contextoTerreno, corrigirCombinacao, acharPlanta,
    normTextura, nativaDe, cultivavel, eEspecie, telaSbnConsorcio, telaSbnAreas,
    REGIOES, regiaoDaUf, biomasDoLugar, criteriosDoLugar, ucsDoLugar, apropriadaZA, REGRAS_UC,
    telaSbnUcs, estadoMapa, gradePlantio, telaSbnMapa, ligarMapa, abrirMapaGis, lerPontos, areaDaArea,
    itensConferencia, conferenciaCsv, telaSbnConferencia, ligarConferencia, CHAVE_SBN, SITUACOES_CONFERENCIA };
  raiz.SBN_LOGICA = api;
})(typeof window !== "undefined" ? window : globalThis);
