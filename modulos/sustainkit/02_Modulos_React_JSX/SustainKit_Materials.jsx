import { useState } from "react";

const C = {
  main:"#1B5E20", light:"#E8F5E9", mid:"#2E7D32", pale:"#F1F8E9",
  white:"#FFFFFF", ink:"#1C2B22", gray:"#F4F7F4", border:"#C8E6C9",
  muted:"#6B7F6E",
};

const MATERIAIS = [
  {nome:"CLT — Madeira Laminada Cruzada",cat:"Estrutura",u:"0,28 W/m²K",co2:"−1,5 kg CO₂e/kg",custo:"R$2.200–3.000/m³",cert:"FSC · LEED MR · EPD",nota:"Carbono negativo. Sequestra CO₂ da atmosfera"},
  {nome:"SIP 100mm (OSB+EPS+OSB)",cat:"Vedação",u:"0,22 W/m²K",co2:"0,08–0,14",custo:"R$1.400–1.900/m²",cert:"LEED · EDGE · RTQ-R",nota:"Melhor relação U-value/custo do mercado BR"},
  {nome:"BTC — Bloco Terra Comprimida",cat:"Vedação",u:"0,80 W/m²K",co2:"0,01–0,03",custo:"R$80–140/m²",cert:"Casa Azul · PBQP-H",nota:"Quase zero carbono. Visual natural único"},
  {nome:"Hempcrete (cânhamo + cal)",cat:"Vedação",u:"0,22 W/m²K",co2:"−0,4 (negativo)",custo:"R$150–250/m²",cert:"LEED · LBC",nota:"Regulação higroscópica excepcional. CO₂ negativo"},
  {nome:"Adobe (terra + palha)",cat:"Vedação",u:"1,00 W/m²K",co2:"0,01",custo:"R$35–60/m²",cert:"PBQP-H Bioconstrução",nota:"Inércia térmica máxima. Autoconstrução possível"},
  {nome:"Bambu Guadua (estrutural)",cat:"Estrutura",u:"—",co2:"−0,8 (negativo)",custo:"R$80–140/colmo",cert:"NBR 16828 · LEED MR",nota:"Resistência 280 MPa tração. Tratamento obrigatório"},
  {nome:"Lã de PET Reciclado",cat:"Isolamento",u:"λ=0,038 W/mK",co2:"0,03–0,06",custo:"R$35–55/m²",cert:"LEED MR · EDGE",nota:"Sem formaldeído."},
  {nome:"Lã de Rocha Mineral",cat:"Isolamento",u:"λ=0,034 W/mK",co2:"0,50–0,80",custo:"R$25–45/m²",cert:"NBR 15575 · LEED",nota:"Incombustível A1. Obrigatória em cobertura de madeira"},
  {nome:"Aerogel (painel 10mm)",cat:"Isolamento",u:"λ=0,015 W/mK",co2:"2,50–4,00",custo:"R$480–960/m²",cert:"Passivhaus · LEED",nota:"Melhor isolante do mercado. 10mm = 50mm lã rocha"},
  {nome:"Vidro duplo câmara ar",cat:"Esquadria",u:"1,20–1,80 W/m²K",co2:"1,20–1,60",custo:"R$180–320/m²",cert:"LEED EQ · RTQ-R",nota:"Reduz perda de calor 4× vs. simples"},
  {nome:"Vidro Low-E",cat:"Esquadria",u:"1,00–1,40 W/m²K",co2:"1,30–1,70",custo:"R$220–380/m²",cert:"LEED EA · EDGE",nota:"Rejeita 30–50% da radiação. Ideal fachadas L/O"},
  {nome:"Vidro eletrocrômico",cat:"Esquadria",u:"0,90–1,20 W/m²K",co2:"3,50–5,00",custo:"R$1.200–2.400/m²",cert:"LEED EA · WELL",nota:"Muda transparência via IoT. LEED Innovation"},
  {nome:"Tadelakt (cal marroquina)",cat:"Revestimento",u:"—",co2:"0,45",custo:"R$280–420/m²",cert:"LEED EQ · WELL · Zero VOC",nota:"Impermeável natural. Zero VOC. Visual luxo"},
  {nome:"Tinta Argila Arpex",cat:"Revestimento",u:"—",co2:"0,05",custo:"R$48/m² (2 demãos)",cert:"LEED EQ · WELL · Zero VOC",nota:"Regulação higroscópica. 70+ cores naturais"},
  {nome:"Telhado verde (sedum)",cat:"Cobertura",u:"0,21 W/m²K",co2:"negativo",custo:"R$220–280/m²",cert:"LEED SS · BREEAM",nota:"Retém 60% da chuva. Isola e é fotografável"},
  {nome:"WPC — Composto Madeira-Plástico",cat:"Revestimento",u:"—",co2:"0,05–0,12",custo:"R$180–340/m²",cert:"LEED MR · EDGE",nota:"100% reciclado pós-consumo. Zero manutenção"},
  {nome:"Geopolímero (concreto)",cat:"Estrutura",u:"—",co2:"0,06–0,10",custo:"Similar convencional",cert:"LEED MR · EPD",nota:"−70–80% CO₂ vs. concreto convencional"},
  {nome:"Madeira TMT (modificada)",cat:"Revestimento",u:"—",co2:"negativo",custo:"R$280–520/m²",cert:"FSC · EPD",nota:"Resistente à umidade sem químicos. 25–40 anos"},
];

const ACABAMENTOS = {
  tadelakt:{nome:"Tadelakt",matM2:115,base:42,ferramentas:680,moM2:280},
  cal:{nome:"Reboco Cal + Fibra",matM2:62,base:0,ferramentas:180,moM2:50},
  argila:{nome:"Tinta Argila Arpex",matM2:48,base:0,ferramentas:80,moM2:20},
  stucco:{nome:"Stucco Veneziano",matM2:220,base:0,ferramentas:220,moM2:320},
  bambu:{nome:"Piso Bambu (BLC)",matM2:160,base:18,ferramentas:120,moM2:45},
};

const ESPECIES = [
  {nome:"Euterpe edulis",pop:"Palmito-juçara",func:"Frutífera · AMEAÇADA · alimenta fauna"},
  {nome:"Cecropia pachystachya",pop:"Embaúba",func:"Pioneira · crescimento rápido · atrai aves"},
  {nome:"Psidium cattleianum",pop:"Araçá",func:"Frutífera nativa · melífera"},
  {nome:"Tibouchina granulosa",pop:"Quaresmeira",func:"Ornamental · floração roxa · melífera"},
  {nome:"Inga edulis",pop:"Ingá",func:"Frutífera · fixa nitrogênio · sombra"},
  {nome:"Passiflora edulis",pop:"Maracujá nativo",func:"Frutífera · melífera · cobertura cercas"},
];

function Card({children,style={},bg=C.white}){
  return <div style={{background:bg,border:`1px solid ${C.border}`,borderRadius:12,
    padding:"16px 18px",boxShadow:"0 2px 10px rgba(27,94,32,0.07)",...style}}>{children}</div>;
}
function Inp({label,value,onChange,unit,min=0,max=9999,step=1}){
  return <div style={{marginBottom:11}}>
    {label&&<div style={{fontSize:11,fontWeight:600,color:C.ink,marginBottom:4}}>{label}</div>}
    <div style={{display:"flex",gap:6,alignItems:"center"}}>
      <input type="number" value={value} min={min} max={max} step={step}
        onChange={e=>onChange(+e.target.value)}
        style={{flex:1,padding:"7px 10px",border:`2px solid ${C.border}`,borderRadius:8,
          fontSize:14,fontWeight:700,color:C.main,background:C.pale,fontFamily:"inherit",outline:"none"}}/>
      {unit&&<span style={{fontSize:11,color:C.muted,minWidth:36}}>{unit}</span>}
    </div>
  </div>;
}
function TabBtn({label,icon,active,onClick}){
  return <button onClick={onClick} style={{padding:"9px 16px",border:"none",background:"transparent",
    cursor:"pointer",color:active?C.white:C.main+"99",fontWeight:active?700:400,fontSize:12,
    fontFamily:"inherit",borderBottom:active?`2px solid ${C.white}`:"2px solid transparent",
    display:"flex",alignItems:"center",gap:5,whiteSpace:"nowrap"}}>
    <span>{icon}</span>{label}
  </button>;
}

function TabMateriais(){
  const [busca,setBusca]=useState("");
  const [cat,setCat]=useState("Todos");
  const [sel,setSel]=useState(null);
  const cats=["Todos",...[...new Set(MATERIAIS.map(m=>m.cat))]];
  const filtrado=MATERIAIS.filter(m=>
    (cat==="Todos"||m.cat===cat)&&
    m.nome.toLowerCase().includes(busca.toLowerCase())
  );
  return(
    <div>
      <Card style={{marginBottom:12,padding:"12px 16px"}}>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}}>
          <input placeholder="🔍 Buscar material..." value={busca} onChange={e=>setBusca(e.target.value)}
            style={{flex:1,minWidth:160,padding:"7px 12px",border:`1px solid ${C.border}`,
              borderRadius:8,fontSize:13,fontFamily:"inherit",outline:"none"}}/>
          {cats.map(c=>(
            <button key={c} onClick={()=>setCat(c)} style={{padding:"5px 12px",borderRadius:20,
              border:`1px solid ${cat===c?C.main:C.border}`,background:cat===c?C.main:"transparent",
              color:cat===c?C.white:C.muted,fontSize:11,fontWeight:600,cursor:"pointer",fontFamily:"inherit"}}>
              {c}
            </button>
          ))}
        </div>
      </Card>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        {filtrado.map(m=>(
          <div key={m.nome} onClick={()=>setSel(sel?.nome===m.nome?null:m)}
            style={{padding:"12px 14px",background:sel?.nome===m.nome?C.pale:C.white,
              borderRadius:10,border:`1px solid ${sel?.nome===m.nome?C.main:C.border}`,cursor:"pointer",transition:"all 0.15s"}}>
            <div style={{fontSize:12,fontWeight:700,color:C.main,marginBottom:3}}>{m.nome}</div>
            <div style={{fontSize:10,color:C.muted,marginBottom:sel?.nome===m.nome?8:0}}>
              <span style={{background:C.light,padding:"1px 6px",borderRadius:10,marginRight:4}}>{m.cat}</span>
              {m.cert}
            </div>
            {sel?.nome===m.nome&&(
              <div>
                {[["U-value / λ",m.u],["CO₂ incorporado",m.co2],["Custo referência",m.custo]].map(([l,v])=>(
                  <div key={l} style={{display:"flex",justifyContent:"space-between",fontSize:11,
                    padding:"4px 0",borderBottom:`1px solid ${C.border}`}}>
                    <span style={{color:C.muted}}>{l}</span>
                    <span style={{fontWeight:600,color:C.main}}>{v}</span>
                  </div>
                ))}
                <div style={{marginTop:6,fontSize:11,color:C.ink,fontStyle:"italic"}}>{m.nota}</div>
              </div>
            )}
          </div>
        ))}
      </div>
      <div style={{textAlign:"center",fontSize:11,color:C.muted,marginTop:10}}>
        {filtrado.length} de {MATERIAIS.length} materiais · Clique para ver detalhes
      </div>
    </div>
  );
}

function TabAcabamentos(){
  const [tipo,setTipo]=useState("tadelakt");
  const [area,setArea]=useState(12);
  const [aplic,setAplic]=useState("prof");
  const ac=ACABAMENTOS[tipo];
  const mat=(ac.matM2+ac.base)*area;
  const mo=aplic==="diy"?0:ac.moM2*area;
  const total=mat+ac.ferramentas+mo;
  return(
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      <Card>
        <div style={{fontWeight:700,color:C.main,marginBottom:12,fontSize:13}}>🎨 Selecionar acabamento</div>
        {Object.entries(ACABAMENTOS).map(([k,a])=>(
          <button key={k} onClick={()=>setTipo(k)} style={{display:"flex",justifyContent:"space-between",
            width:"100%",padding:"10px 14px",borderRadius:9,marginBottom:6,textAlign:"left",
            cursor:"pointer",fontFamily:"inherit",border:`1px solid ${tipo===k?C.main:C.border}`,
            background:tipo===k?C.pale:C.white}}>
            <span style={{fontSize:13,fontWeight:tipo===k?700:400,color:tipo===k?C.main:C.ink}}>{a.nome}</span>
            <span style={{fontSize:11,color:C.muted}}>~R${a.matM2}/m²</span>
          </button>
        ))}
        <Inp label="Área a revestir (m²)" value={area} onChange={setArea} unit="m²" min={1} max={2000}/>
        <div style={{display:"flex",gap:6}}>
          {[["prof","Profissional"],["diy","DIY"]].map(([v,l])=>(
            <button key={v} onClick={()=>setAplic(v)} style={{flex:1,padding:"7px",borderRadius:8,
              border:`1px solid ${aplic===v?C.main:C.border}`,background:aplic===v?C.pale:C.white,
              color:aplic===v?C.main:C.muted,fontWeight:aplic===v?700:400,fontSize:11,
              cursor:"pointer",fontFamily:"inherit"}}>{l}</button>
          ))}
        </div>
      </Card>
      <Card bg={C.pale}>
        <div style={{fontWeight:700,color:C.main,marginBottom:10,fontSize:13}}>💰 Orçamento</div>
        {[["Material + base","R$ "+mat.toLocaleString("pt-BR",{minimumFractionDigits:0})],
          ["Kit ferramentas","R$ "+ac.ferramentas.toLocaleString("pt-BR")],
          ["Mão de obra",aplic==="diy"?"R$ 0 (DIY)":"R$ "+mo.toLocaleString("pt-BR")]].map(([l,v])=>(
          <div key={l} style={{display:"flex",justifyContent:"space-between",padding:"8px 10px",
            background:C.white,borderRadius:7,marginBottom:5,border:`1px solid ${C.border}`}}>
            <span style={{fontSize:12,color:C.ink}}>{l}</span>
            <span style={{fontSize:13,fontWeight:700,color:C.main}}>{v}</span>
          </div>
        ))}
        <div style={{padding:"14px",background:C.main,borderRadius:10,marginTop:8,textAlign:"center"}}>
          <div style={{fontSize:11,color:"rgba(255,255,255,0.7)",marginBottom:2}}>TOTAL</div>
          <div style={{fontSize:26,fontWeight:800,color:C.white}}>
            R$ {total.toLocaleString("pt-BR",{minimumFractionDigits:0})}
          </div>
          <div style={{fontSize:11,color:"rgba(255,255,255,0.6)",marginTop:2}}>
            R$ {Math.round(total/area).toLocaleString("pt-BR")} / m²
          </div>
        </div>
        {aplic==="diy"&&(
          <div style={{marginTop:8,padding:"8px",background:"#C8E6C9",borderRadius:7,
            fontSize:11,color:"#1B5E20",fontStyle:"italic"}}>
            ✅ Economia de R$ {(ac.moM2*area).toLocaleString("pt-BR")} em mão de obra no DIY
          </div>
        )}
      </Card>
    </div>
  );
}

function TabEcologia(){
  const [mudas,setMudas]=useState(ESPECIES.map(e=>({...e,qtd:5})));
  const totalMudas=mudas.reduce((a,e)=>a+e.qtd,0);
  const co2Materiais=[
    {mat:"CLT 12m³",co2:-18000},{mat:"SIP 80m²",co2:640},
    {mat:"BTC 200un",co2:4},{mat:"Concreto cinza 15m³",co2:3150},
    {mat:"Bambu 20 colmos",co2:-800},{mat:"Lã PET 150m²",co2:7.5},
  ];
  const totalCo2=co2Materiais.reduce((a,m)=>a+m.co2,0);
  return(
    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
      <Card>
        <div style={{fontWeight:700,color:C.main,marginBottom:4,fontSize:13}}>🌿 Paisagismo Nativo — Mata Atlântica</div>
        <div style={{fontSize:11,color:C.muted,marginBottom:10}}>Requisito LEED v5 — mínimo 50% espécies nativas</div>
        {mudas.map((e,i)=>(
          <div key={i} style={{display:"flex",alignItems:"center",gap:8,marginBottom:7,
            padding:"8px 10px",background:C.pale,borderRadius:8}}>
            <div style={{flex:1}}>
              <div style={{fontSize:11,fontWeight:600,color:C.main,fontStyle:"italic"}}>{e.nome}</div>
              <div style={{fontSize:10,color:C.muted}}>{e.pop} · {e.func}</div>
            </div>
            <input type="number" value={e.qtd} min={0} max={1000}
              onChange={ev=>setMudas(m=>m.map((x,j)=>j===i?{...x,qtd:+ev.target.value}:x))}
              style={{width:60,padding:"4px 8px",border:`2px solid ${C.border}`,borderRadius:7,
                fontSize:13,fontWeight:700,color:C.main,background:C.white,
                fontFamily:"inherit",textAlign:"center",outline:"none"}}/>
            <span style={{fontSize:10,color:C.muted}}>mudas</span>
          </div>
        ))}
        <div style={{padding:"10px",background:C.main,borderRadius:8,textAlign:"center",marginTop:4}}>
          <div style={{fontSize:13,fontWeight:800,color:C.white}}>{totalMudas} mudas nativas planejadas</div>
          <div style={{fontSize:10,color:"rgba(255,255,255,0.7)",marginTop:2}}>
            {totalMudas>=50?"✅ Atende meta LEED v5":"⚠️ Meta: mínimo 50 mudas"}
          </div>
        </div>
      </Card>
      <Card bg={C.pale}>
        <div style={{fontWeight:700,color:C.main,marginBottom:10,fontSize:13}}>♻️ Carbono Incorporado (LCA simplificado)</div>
        <div style={{fontSize:11,color:C.muted,marginBottom:8}}>LEED v5 — EPD obrigatória para materiais principais</div>
        {co2Materiais.map(m=>(
          <div key={m.mat} style={{display:"flex",justifyContent:"space-between",alignItems:"center",
            padding:"7px 10px",background:m.co2<0?"#C8E6C9":"#FFF9C4",
            borderRadius:7,marginBottom:5,border:`1px solid ${C.border}`}}>
            <span style={{fontSize:11,color:C.ink}}>{m.mat}</span>
            <span style={{fontSize:12,fontWeight:700,color:m.co2<0?"#1B5E20":"#E65100"}}>
              {m.co2>0?"+":""}{m.co2.toLocaleString("pt-BR")} kg CO₂e
            </span>
          </div>
        ))}
        <div style={{padding:"12px",background:totalCo2<0?"#C8E6C9":"#FFCDD2",
          borderRadius:8,marginTop:4,textAlign:"center"}}>
          <div style={{fontSize:13,fontWeight:800,color:totalCo2<0?"#1B5E20":"#B71C1C"}}>
            {totalCo2>0?"+":""}{totalCo2.toLocaleString("pt-BR")} kg CO₂e
          </div>
          <div style={{fontSize:11,color:totalCo2<0?"#2E7D32":"#C62828",marginTop:2}}>
            {totalCo2<0?"✅ Carbono negativo — sequestra mais do que emite":"⚠️ Revisar especificação de materiais"}
          </div>
        </div>
        <div style={{fontSize:10,color:C.muted,marginTop:6,fontStyle:"italic"}}>
          Fonte: EPDs dos fabricantes + ABNT + IBÀ + World Steel Association 2024
        </div>
      </Card>
    </div>
  );
}

const TABS=[
  {id:"mat",icon:"🧱",label:"Banco de Materiais",comp:TabMateriais},
  {id:"acab",icon:"🎨",label:"Acabamentos",comp:TabAcabamentos},
  {id:"eco",icon:"🌿",label:"Ecologia",comp:TabEcologia},
];

export default function App(){
  const [tab,setTab]=useState("mat");
  const Tab=TABS.find(t=>t.id===tab).comp;
  return(
    <div style={{fontFamily:"-apple-system,'Segoe UI',Arial,sans-serif",background:"#F1F8E9",minHeight:"100vh"}}>
      <div style={{background:C.main,padding:"14px 20px 0"}}>
        <div style={{maxWidth:900,margin:"0 auto"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:14}}>
            <div style={{display:"flex",alignItems:"center",gap:10}}>
              <div style={{width:32,height:32,borderRadius:"50%",background:"rgba(255,255,255,0.2)",
                display:"flex",alignItems:"center",justifyContent:"center",fontSize:16}}>🧱</div>
              <div>
                <div style={{fontWeight:800,fontSize:16,color:C.white}}>SustainKit Materials</div>
                <div style={{fontSize:10,color:"rgba(255,255,255,0.7)"}}>Physis Engineering · Materiais, Acabamentos e Ecologia</div>
              </div>
            </div>
            <div style={{background:"rgba(255,255,255,0.15)",borderRadius:6,padding:"3px 12px",
              fontSize:11,fontWeight:700,color:C.white}}>v1.0</div>
          </div>
          <div style={{display:"flex",gap:2}}>
            {TABS.map(t=><TabBtn key={t.id} icon={t.icon} label={t.label} active={tab===t.id} onClick={()=>setTab(t.id)}/>)}
          </div>
        </div>
      </div>
      <div style={{maxWidth:900,margin:"16px auto",padding:"0 16px"}}><Tab/></div>
      <div style={{textAlign:"center",padding:"12px",fontSize:10,color:C.muted}}>
        Physis Engineering · LEED v5 · FSC · EPD ISO 14025 · ABNT NBR
      </div>
    </div>
  );
}
