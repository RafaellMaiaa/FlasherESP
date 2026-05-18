const socket = io();

const term = new Terminal({
    theme: { background: '#000000', foreground: '#a1a1aa', cursor: '#0ea5e9', selection: '#27272a' },
    fontFamily: "'JetBrains Mono', monospace", fontSize: 13, letterSpacing: 0,
    convertEol: true, disableStdin: true, cursorBlink: true
});

let monitorConnected = false;
let isAdmin = false;
let perfisList = [];
let logHistory = [];
let perfilAtivo = null;
let isAutoModeRunning = false;
let etiquetaAtiva = localStorage.getItem('etiquetaAtiva') || null;
let modalConfirmObj;

document.addEventListener("DOMContentLoaded", () => {
    term.open(document.getElementById('terminal-container'));
    term.writeln('\x1b[1;36m[ INIT ]\x1b[0m Sistema de Produção Operacional.');

    modalConfirmObj = new bootstrap.Modal(document.getElementById('modalConfirmacao'));
    const ipInput = document.getElementById('ip-impressora');
    if(ipInput) {
        ipInput.value = localStorage.getItem('ipImpressora') || "";
        ipInput.addEventListener('input', () => localStorage.setItem('ipImpressora', ipInput.value));
    }
    
    carregarPortas(); 
    carregarArquivos(false); 
    carregarEtiquetas();
    carregarDadosPerfis();
    aplicarEstadoPreferencias();
});

function showToast(msg, type = "success") {
    let bgColor = type === "success" ? "#059669" : (type === "error" ? "#dc2626" : "#d97706");
    Toastify({ 
        text: msg, duration: 3000, close: true, gravity: "top", position: "right", 
        style: { background: bgColor, borderRadius: "4px", fontWeight: "500", fontSize: "13px", boxShadow: "0 4px 12px rgba(0,0,0,0.5)", border: "1px solid rgba(255,255,255,0.1)" } 
    }).showToast();
}

function updateStatus(text, colorClass) {
    const el = document.getElementById('status-text');
    el.innerText = text;
    el.style.color = colorClass === 'success' ? 'var(--accent)' : (colorClass === 'error' ? 'var(--danger)' : 'var(--warning)');
}

function abrirModal(id) {
    const m = document.getElementById(id);
    if (m) { let modal = bootstrap.Modal.getInstance(m) || new bootstrap.Modal(m); modal.show(); }
}

function limparTerminal() { term.clear(); }

function limparCamposLeitura() {
    window.beepTocado = false;
    ['input-mac', 'input-sn', 'input-imei', 'input-cimi'].forEach(id => {
        let el = document.getElementById(id);
        if(el) { el.value = ""; el.style.borderColor = "var(--border)"; el.style.color = "var(--text-main)"; }
    });
}

function showPanel(id) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    
    const targetBtn = Array.from(document.querySelectorAll('.nav-btn')).find(b => b.getAttribute('onclick') === `showPanel('${id}')`);
    if(targetBtn) targetBtn.classList.add('active');
    
    const panel = document.getElementById(id);
    if(panel) panel.classList.add('active');
    
    if (id === 'painel-flash') carregarPortas();
    else if (id === 'painel-arquivos') carregarArquivos();
    else if (id === 'painel-perfis') carregarDadosPerfis();
    else if (id === 'painel-etiquetas') carregarEtiquetas();
    else if (id === 'painel-logs') carregarLogsDoCSV();
}

async function carregarPortas() {
    try { 
        const res = await fetch('/listar_portas'); const dados = await res.json(); 
        const sel = document.getElementById('selectPorta'); const atual = sel.value; 
        sel.innerHTML = ""; 
        dados.forEach(p => sel.add(new Option(p.device, p.device))); 
        if (atual) sel.value = atual; 
    } catch(e) {}
}

function toggleMonitor() {
    const porta = document.getElementById('selectPorta').value;
    const baud = document.getElementById('selectBaud').value;
    if (!monitorConnected) { 
        if (!porta) return showToast("[ ERRO ] Selecione uma porta.", "error");
        socket.emit('iniciar_monitor', { porta, baud }); 
    } else { socket.emit('parar_monitor'); }
}

function iniciar(modo) {
    if (monitorConnected) toggleMonitor(); 
    const porta = document.getElementById('selectPorta').value;
    const ficheiro = document.getElementById('selectFicheiro').value;
    const baud = document.getElementById('selectBaud').value;
    
    if (!porta) return showToast("[ ERRO ] Porta COM não selecionada", "error");
    if (modo === 'flash_limpo' && !ficheiro) return showToast("[ ERRO ] Firmware não selecionado", "error");
    
    updateStatus("A GRAVAR FLASH...", "warning");
    term.clear(); term.writeln(`\x1b[1;33m[ EXEC ] Iniciando processo na porta ${porta} @ ${baud} baud\x1b[0m`);
    limparCamposLeitura();
    socket.emit('iniciar_processo', { porta, baud, ficheiro, modo });
}

function iniciarAutomacaoMES() {
    const ficheiro = document.getElementById('selectFicheiro').value;
    const porta = document.getElementById('selectPorta').value;
    const etiquetaUsar = perfilAtivo ? perfilAtivo.zpl : etiquetaAtiva;

    if (!porta) return showToast("[ AVISO ] Selecione porta COM", "warning");
    if (!ficheiro && !perfilAtivo) return showToast("[ AVISO ] Selecione firmware ou perfil", "warning");
    if (!etiquetaUsar) return showToast("[ ERRO ] Molde ZPL em falta", "error");
    
    const btn = document.getElementById('btn-automacao');
    btn.disabled = true; btn.innerText = "A PROCESSAR...";

    isAutoModeRunning = true;
    term.writeln('\x1b[1;35m[ MODO MES ] Ciclo automático iniciado\x1b[0m');
    iniciar('flash_limpo'); 
}

function resetBotaoAutomacao() {
    const btn = document.getElementById('btn-automacao');
    btn.disabled = false; btn.className = "btn btn-mega w-100 py-3 mb-2"; btn.innerText = "FLUXO AUTOMÁTICO";
    btn.onclick = iniciarAutomacaoMES;
}

socket.on('log_flash', msg => term.write(msg.data));
socket.on('log_monitor', msg => term.write(msg.data));
socket.on('status_monitor', msg => {
    const btn = document.getElementById('btn-monitor'); monitorConnected = msg.ativo;
    if (msg.ativo) { btn.innerText = 'MONITOR: ON'; btn.className = 'btn btn-sm btn-danger font-monospace'; term.writeln(`\n\x1b[1;36m[ INFO ] Monitor aberto em ${msg.msg}\x1b[0m\n`); } 
    else { btn.innerText = 'MONITOR: OFF'; btn.className = 'btn btn-sm btn-outline-secondary font-monospace'; }
});

socket.on('fim_processo', () => { 
    updateStatus("FLASH CONCLUÍDO", "success");
    term.writeln('\n\x1b[1;32m[ OK ] Processo terminado com sucesso\x1b[0m');
    if (isAutoModeRunning) {
        term.writeln('\x1b[1;33m[ AVISO ] A aguardar boot da placa...\x1b[0m');
        socket.emit('iniciar_monitor', { porta: document.getElementById('selectPorta').value, baud: 115200 }); 
        const btn = document.getElementById('btn-automacao');
        btn.disabled = false; btn.className = "btn btn-mega w-100 py-3 mb-2"; btn.style.backgroundColor = "var(--accent)";
        btn.innerText = "VALIDAR DADOS"; btn.onclick = dadosEncontradosAvançar;
    }
});

socket.on('dados_capturados', dados => { 
    let alterou = false;
    if (dados.mac && !document.getElementById('input-mac').value) { document.getElementById('input-mac').value = dados.mac.replace(/:/g, '').toLowerCase(); document.getElementById('input-mac').style.borderColor = "var(--accent)"; alterou = true; }
    if (dados.imei && !document.getElementById('input-imei').value) { document.getElementById('input-imei').value = dados.imei; document.getElementById('input-imei').style.borderColor = "var(--accent)"; alterou = true; }
    if (dados.cimi && !document.getElementById('input-cimi').value) { document.getElementById('input-cimi').value = dados.cimi; document.getElementById('input-cimi').style.borderColor = "var(--accent)"; alterou = true; }
    if (dados.serial && !document.getElementById('input-sn').value) { document.getElementById('input-sn').value = dados.serial; alterou = true; }
    
    if(alterou && document.getElementById('input-mac').value.length > 5 && !window.beepTocado) {
        showToast("[ LOG ] Dados Extraídos", "success"); tocarSomSucesso(); window.beepTocado = true;
    }
});

function dadosEncontradosAvançar() {
    let inMac = document.getElementById('input-mac').value;
    if (!inMac || inMac.length < 5) if(!confirm("Aviso: MAC Address ausente. Prosseguir?")) return;
    if (monitorConnected) toggleMonitor(); 
    
    document.getElementById('mod-mac').value = document.getElementById('input-mac').value;
    document.getElementById('mod-imei').value = document.getElementById('input-imei').value;
    document.getElementById('mod-cimi').value = document.getElementById('input-cimi').value;
    let painelSN = document.getElementById('input-sn').value;
    if (!painelSN) painelSN = Math.floor(Math.random() * 9000000000) + 1000000000;
    document.getElementById('mod-sn').value = painelSN;
    
    modalConfirmObj.show();
}

function cancelarAutomacao() { isAutoModeRunning = false; limparCamposLeitura(); resetBotaoAutomacao(); }

async function concluirFluxoAutomatico() {
    modalConfirmObj.hide(); isAutoModeRunning = false;
    const payload = {
        mac: document.getElementById('mod-mac').value, sn: document.getElementById('mod-sn').value,
        imei: document.getElementById('mod-imei').value, cimi: document.getElementById('mod-cimi').value,
        perfil: perfilAtivo ? perfilAtivo.nome : "Manual"
    };
    const qtd = document.getElementById('mod-qtd').value;
    const etiquetaUsar = perfilAtivo ? perfilAtivo.zpl : etiquetaAtiva;

    try {
        await fetch('/guardar_csv_manual', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
        carregarLogsDoCSV();
        await enviarParaMotorZPL(payload.mac, payload.sn, payload.imei, payload.cimi, etiquetaUsar, qtd);
        term.writeln('\n\x1b[1;32m[ SUCESSO ] Ciclo completo e dados gravados.\x1b[0m');
    } catch(e) { term.writeln(`\n\x1b[1;31m[ ERRO ] ${e.message}\x1b[0m`); showToast("[ ERRO ] Falha crítica", "error"); 
    } finally { resetBotaoAutomacao(); }
}

async function enviarParaMotorZPL(mac, sn, imei, cimi, label_file, qtd) {
    const ip = document.getElementById('ip-impressora').value.trim();
    const resposta = await fetch('/api/processar_zpl_v6', { 
        method: 'POST', headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ mac, imei, sn, cimi, label_file, ip_impressora: ip, quantidade: qtd }) 
    });
    const jsonZpl = await resposta.json();
    if (jsonZpl.sucesso) {
        if (jsonZpl.impresso_direto) { term.writeln(`\x1b[1;32m[ IMPRESSÃO ] Enviadas ${qtd} unidades para ${ip}\x1b[0m`); showToast(`[ OK ] Impressão enviada`, "success"); } 
        else {
            const blob = new Blob([jsonZpl.zpl], {type:'text/plain'}); const a = document.createElement('a');
            a.href = window.URL.createObjectURL(blob); a.download = `Etiquetas_${sn}_x${qtd}.zpl`; a.click();
            term.writeln(`\x1b[1;32m[ ZPL ] Ficheiro gerado e transferido\x1b[0m`); showToast("[ OK ] Ficheiro ZPL Baixado", "success");
        }
    } else { showToast("[ ERRO ] Falha ZPL", "error"); term.writeln(`\x1b[1;31m[ ERRO IMPRESSORA ] ${jsonZpl.erro}\x1b[0m`); }
}

async function carregarArquivos(renderList = true) { 
    const resB = await fetch('/listar_ficheiros?t=' + new Date().getTime()); const bins = await resB.json(); 
    const selMain = document.getElementById('selectFicheiro'); const selPerfil = document.getElementById('p-file');
    if(selMain) { const atual = selMain.value; selMain.innerHTML = ""; bins.forEach(f => selMain.add(new Option(f, f))); if(atual) selMain.value = atual; }
    if(selPerfil) { selPerfil.innerHTML = ""; bins.forEach(f => selPerfil.add(new Option(f, f))); }
    if (renderList) { 
        const lista = document.getElementById('listaFiles'); lista.innerHTML = ""; 
        bins.forEach(f => { lista.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center"><span class="font-monospace"><i class="fas fa-file-code me-2"></i>${f}</span><button class="btn btn-sm btn-outline-danger admin-only" onclick="apagarArquivo('${f}', 'bin')"><i class="fas fa-trash"></i></button></li>`; }); 
    } 
}

async function carregarEtiquetas() {
    const resZ = await fetch('/listar_etiquetas?t=' + new Date().getTime()); const zpls = await resZ.json();
    const selZpl = document.getElementById('p-zpl');
    if(selZpl) { selZpl.innerHTML = "<option value=''>Nenhuma</option>"; zpls.forEach(f => selZpl.add(new Option(f, f))); }
    const lista = document.getElementById('listaEtiquetas'); lista.innerHTML = "";
    if (zpls.length === 0) { lista.innerHTML = "<li class='list-group-item text-muted border-0'>Lista vazia.</li>"; return; }
    zpls.forEach(f => {
        const isAtiva = (f === etiquetaAtiva);
        lista.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center ${isAtiva ? 'border-success' : ''}"><span class="font-monospace"><i class="fas fa-tag me-2 ${isAtiva ? 'text-success' : 'text-muted'}"></i>${f}</span><div><button class="btn btn-sm ${isAtiva ? 'btn-success' : 'btn-outline-secondary'} me-2" onclick="ativarEtiquetaManual('${f}')">${isAtiva ? 'Ativa' : 'Usar'}</button><button class="btn btn-sm btn-outline-danger admin-only" onclick="apagarArquivo('${f}', 'zpl')"><i class="fas fa-trash"></i></button></div></li>`;
    });
}

async function uploadArquivo(inputId, urlRota) { 
    const input = document.getElementById(inputId); 
    if (!input || input.files.length === 0) return showToast("[ AVISO ] Selecione ficheiro", "warning");
    const fd = new FormData(); fd.append('file', input.files[0]); 
    try {
        const res = await fetch(urlRota, { method: 'POST', body: fd }); 
        if (res.ok) { 
            const jsonResposta = await res.json(); input.value = ""; 
            if (jsonResposta.sucesso) { showToast("[ OK ] Upload concluído", "success"); urlRota.includes('etiqueta') ? carregarEtiquetas() : carregarArquivos(); } 
            else showToast(`[ ERRO ] ${jsonResposta.erro || "Upload falhou"}`, "error");
        } else showToast("[ ERRO ] Servidor inacessível", "error");
    } catch (e) { showToast(`[ ERRO ] ${e.message}`, "error"); }
}

async function apagarArquivo(nome, tipo) { 
    if (!confirm(`Remover ficheiro: "${nome}"?`)) return;
    const rota = tipo === 'zpl' ? '/delete_etiqueta' : '/delete_file';
    await fetch(rota, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({filename: nome}) }); 
    if (tipo === 'zpl') { if (etiquetaAtiva === nome) { etiquetaAtiva = null; localStorage.removeItem('etiquetaAtiva'); } carregarEtiquetas(); } else carregarArquivos();
}

function ativarEtiquetaManual(nome) { 
    if(perfilAtivo) return showToast("[ AVISO ] Cancele perfil ativo primeiro", "warning");
    etiquetaAtiva = nome; localStorage.setItem('etiquetaAtiva', nome); carregarEtiquetas(); 
}

async function carregarDadosPerfis() {
    await carregarArquivos(false); await carregarEtiquetas(); 
    const res = await fetch('/api/perfis?t=' + new Date().getTime()); perfisList = await res.json();
    const container = document.getElementById('grid-perfis'); container.innerHTML = "";
    if (perfisList.length === 0) { container.innerHTML = `<div class='col-12 text-muted font-monospace'>[ INFO ] Nenhum perfil configurado.</div>`; return; }
    perfisList.forEach(p => {
        let btnDelete = isAdmin ? `<button class="btn btn-sm btn-outline-danger ms-auto" onclick="apagarPerfil(${p.id})"><i class="fas fa-trash"></i></button>` : '';
        container.innerHTML += `<div class="col-md-4 mb-4"><div class="custom-card h-100"><h5 class="fw-bold mb-3" style="color:var(--text-main); font-size:14px;">${p.nome}</h5><div class="font-monospace text-muted mb-4"><div class="mb-2"><i class="fas fa-microchip me-2 opacity-50"></i>${p.file}</div><div><i class="fas fa-tag me-2 opacity-50"></i>${p.zpl || 'Sem ZPL'}</div></div><div class="d-flex"><button class="btn btn-sm btn-outline-secondary fw-bold" onclick='ativarPerfil(${JSON.stringify(p)})'>Aplicar Perfil</button>${btnDelete}</div></div></div>`;
    });
}
function ativarPerfil(p) {
    perfilAtivo = p; document.getElementById('selectFicheiro').value = p.file; document.getElementById('selectBaud').value = p.baud;
    document.getElementById('selectFicheiro').disabled = true; document.getElementById('selectBaud').disabled = true; 
    showPanel('painel-flash'); showToast(`[ OK ] Perfil ${p.nome} carregado`, "success");
}
async function tentarLoginAdmin() {
    const res = await fetch('/api/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ password: document.getElementById('admin-pwd').value }) });
    const data = await res.json();
    if (data.sucesso) { isAdmin = true; document.body.classList.add('is-admin'); document.getElementById('admin-pwd').value = ""; showToast("[ OK ] Acesso Concedido", "success"); carregarDadosPerfis(); showPanel('painel-perfis'); } 
    else showToast("[ ERRO ] Credenciais inválidas", "error");
}
async function sairAdmin() { await fetch('/api/logout', { method: 'POST' }); isAdmin = false; document.body.classList.remove('is-admin'); showToast("[ INFO ] Sessão encerrada", "warning"); showPanel('painel-flash'); }

async function carregarLogsDoCSV() { 
    try { const res = await fetch('/api/logs?t=' + new Date().getTime()); logHistory = await res.json(); renderizarTabelaLogs(); } catch(e) {}
}

function renderizarTabelaLogs() {
    const tbody = document.getElementById('table-logs-body'); 
    tbody.innerHTML = "";
    if (logHistory.length === 0) { 
        tbody.innerHTML = "<tr><td colspan='7' class='text-muted py-4 px-4'>[ INFO ] Nenhum registo encontrado.</td></tr>"; 
        return; 
    } 
    logHistory.forEach((l, i) => {
        let btnApagar = `<button class="btn btn-sm btn-outline-danger" onclick="apagarLinhaUnicaCSV(${i})"><i class="fas fa-trash"></i></button>`;
        tbody.innerHTML = `
        <tr>
            <td class="px-4" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel); color: #e4e4e7;">${l.Data}</td>
            <td class="px-4" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel); color: #ffffff; font-weight: 600;">${l.MAC}</td>
            <td class="px-4" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel); color: var(--warning);">${l.Serial || '-'}</td>
            <td class="px-4" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel); color: #e4e4e7;">${l.IMEI}</td>
            <td class="px-4" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel); color: #e4e4e7;">${l.CIMI || '-'}</td>
            <td class="px-4" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel); color: #e4e4e7;">${l.Perfil || "N/A"}</td>
            <td class="px-4 admin-only text-end" style="border-bottom: 1px solid var(--border); background-color: var(--bg-panel);">${btnApagar}</td>
        </tr>` + tbody.innerHTML;
    });
}

function gerarNovoSN(campoId) { document.getElementById(campoId).value = Math.floor(Math.random() * 9000000000) + 1000000000; }
function aplicarEstadoPreferencias() {
    const tutAtivos = localStorage.getItem('tutoriaisAtivos') !== 'false';
    document.querySelectorAll('.btn-tutorial').forEach(btn => btn.style.setProperty('display', tutAtivos ? 'inline-flex' : 'none', 'important'));
}
function tocarSomSucesso() {
    if (localStorage.getItem('somAtivo') === 'false') return;
    try { const ctx = new (window.AudioContext || window.webkitAudioContext)(); const osc = ctx.createOscillator(); osc.connect(ctx.destination); osc.frequency.setValueAtTime(880, ctx.currentTime); osc.start(); osc.stop(ctx.currentTime + 0.1); } catch(e) {}
}

function fecharAplicacao() { 
    // Subtrai o ecrã instantaneamente
    document.body.innerHTML = `
    <div style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: #000000; z-index: 9999; display: flex; flex-direction: column; align-items: center; justify-content: center;">
        <i class="fas fa-power-off" style="font-size: 48px; color: #3f3f46; margin-bottom: 24px;"></i>
        <h2 style="font-family: 'JetBrains Mono', monospace; font-size: 18px; color: #e4e4e7; letter-spacing: 2px; font-weight: normal;">[ SYSTEM HALTED ]</h2>
        <p style="font-family: 'Inter', sans-serif; color: #52525b; font-size: 13px; margin-top: 8px;">A ligação ao servidor foi cortada com segurança.</p>
    </div>`;
    
    // Pede ao servidor para desligar, mas ignora a resposta/erro de rede
    fetch('/shutdown', { method: 'POST' }).catch(() => {});
    
    // Bloqueia qualquer atualização da página para evitar o ecrã feio do Chrome
    window.stop();
    
    // Fecha a janela ao fim de 2.5 segundos
    setTimeout(() => { window.close(); }, 2500); 
}