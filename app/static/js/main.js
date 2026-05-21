const socket = io();
const consola = document.getElementById('consola');

// Variáveis Globais de Estado
let activeTab = 'install';
let monitorConnected = false;
let isAdmin = false;
let perfisList = [];
let logHistory = [];
let perfilAtivo = null;

let isAutoModeRunning = false;
let checkDataInterval = null;
let autoTimeout = null;

let flashStartTime = 0;
let flashTimerInterval = null;

let etiquetaAtiva = localStorage.getItem('etiquetaAtiva') || null;

// Inicialização segura do DOM
let modalResetObj;
let modalConfirmObj;
let modalPrepFlashObj;
let modalErroFlashObj;

document.addEventListener("DOMContentLoaded", () => {
    modalResetObj = new bootstrap.Modal(document.getElementById('modalReset'));
    modalConfirmObj = new bootstrap.Modal(document.getElementById('modalConfirmacao'));
    modalPrepFlashObj = new bootstrap.Modal(document.getElementById('modalPrepFlash'));
    modalErroFlashObj = new bootstrap.Modal(document.getElementById('modalErroFlash'));
    
    const ipInput = document.getElementById('ip-impressora');
    if(ipInput) {
        ipInput.value = localStorage.getItem('ipImpressora') || "";
        ipInput.addEventListener('input', () => localStorage.setItem('ipImpressora', ipInput.value));
    }
    
    carregarPortas(); 
    carregarArquivos(false); 
    carregarEtiquetas();
    carregarDadosPerfis();
    atualizarBadges();
    aplicarEstadoPreferencias();
});

// --- UI / UX (TOASTS E TEMPORIZADORES) ---
function showToast(msg, type = "success") {
    let bgColor = type === "success" ? "#10b981" : (type === "error" ? "#ef4444" : "#f59e0b");
    Toastify({
        text: msg,
        duration: 3000,
        close: true,
        gravity: "top", 
        position: "right", 
        style: { background: bgColor, borderRadius: "8px", fontWeight: "bold" }
    }).showToast();
}

function startTimer() {
    const timerBadge = document.getElementById('flash-timer');
    if(timerBadge) {
        timerBadge.style.display = 'inline-block';
        timerBadge.className = 'badge bg-primary';
        flashStartTime = Date.now();
        flashTimerInterval = setInterval(() => {
            const diff = (Date.now() - flashStartTime) / 1000;
            timerBadge.innerText = diff.toFixed(1) + "s";
        }, 100);
    }
}

function stopTimer(sucesso) {
    clearInterval(flashTimerInterval);
    const timerBadge = document.getElementById('flash-timer');
    if(timerBadge) {
        timerBadge.className = sucesso ? 'badge bg-success' : 'badge bg-danger';
    }
}

function checkInputVisuals() {
    ['input-mac', 'input-imei', 'input-cimi'].forEach(id => {
        let el = document.getElementById(id);
        if(el && el.value.length > 5) {
            el.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
            el.style.borderColor = 'var(--success)';
            el.style.color = 'var(--success)';
        }
    });
}

// --- NAVEGAÇÃO BÁSICA ---
function toggleSidebar() { document.querySelector('.sidebar').classList.toggle('expanded'); }

function showPanel(id) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    
    const navMap = {
        'painel-flash': 0, 'painel-offline': 1, 'painel-perfis': 2, 
        'painel-arquivos': 3, 'painel-etiquetas': 4, 'painel-logs': 5,
        'painel-definicoes': 6
    };
    
    const buttons = document.querySelectorAll('.nav-btn');
    if (buttons[navMap[id]]) buttons[navMap[id]].classList.add('active');
    document.getElementById(id).classList.add('active');
    
    if (id === 'painel-flash') { carregarPortas(); carregarArquivos(); }
    else if (id === 'painel-arquivos') carregarArquivos();
    else if (id === 'painel-perfis') carregarDadosPerfis();
    else if (id === 'painel-etiquetas') {
        carregarEtiquetas().then(() => {
            const lista = document.getElementById('listaEtiquetas');
            const tutAtivos = localStorage.getItem('tutoriaisAtivos') !== 'false';
            // Se os tutoriais estão ligados e não há etiquetas, abre o modal
            if (tutAtivos && (!lista || lista.children.length === 0 || lista.innerHTML.includes('Vazio.'))) {
                abrirModal('modalTutorialZPL');
            }
        });
    }
    else if (id === 'painel-logs') carregarLogsDoCSV();
}

function switchConsole(mode) {
    activeTab = mode;
    document.querySelectorAll('.console-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + mode).classList.add('active');
    
    document.getElementById('tools-install').style.setProperty('display', mode==='install'?'flex':'none', 'important');
    document.getElementById('tools-monitor').style.setProperty('display', mode==='monitor'?'flex':'none', 'important');
    
    if (mode === 'monitor') consola.classList.add('serial-mode');
    else consola.classList.remove('serial-mode');
    
    consola.scrollTop = consola.scrollHeight;
}

function limparEcra() { consola.innerHTML = ""; document.getElementById('barra').style.width = "0%"; }

function guardarLogs() { 
    const blob = new Blob([consola.innerText], {type:'text/plain'});
    const a = document.createElement('a'); 
    a.href = URL.createObjectURL(blob);
    a.download = (activeTab === 'install' ? 'flash_log_' : 'serial_log_') + Date.now() + ".txt";
    a.click();
}

async function tentarLoginAdmin() {
    const pwdInput = document.getElementById('admin-pwd').value;
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ password: pwdInput })
        });
        const data = await res.json();

        if (data.sucesso) {
            isAdmin = true;
            document.body.classList.add('is-admin');
            
            const loginSec = document.getElementById('admin-login-section');
            const logoutSec = document.getElementById('admin-logout-section');
            if(loginSec) loginSec.style.display = 'none';
            if(logoutSec) logoutSec.style.display = 'block';

            showToast("Modo Administrador Desbloqueado!", "success");
            document.getElementById('admin-pwd').value = "";
            carregarDadosPerfis();
            carregarLogsDoCSV();
            showPanel('painel-perfis'); 
        } else {
            showToast("Senha incorreta.", "error");
        }
    } catch (e) {
        showToast("Erro de comunicação com o servidor.", "error");
    }
}

async function sairAdmin() {
    await fetch('/api/logout', { method: 'POST' });
    isAdmin = false;
    document.body.classList.remove('is-admin');
    
    const loginSec = document.getElementById('admin-login-section');
    const logoutSec = document.getElementById('admin-logout-section');
    if(loginSec) loginSec.style.display = 'block';
    if(logoutSec) logoutSec.style.display = 'none';

    showToast("Sessão de Administrador Encerrada.", "warning");
    carregarDadosPerfis(); 
    showPanel('painel-flash'); 
}


// --- UTILIDADES ---
function gerarNovoSN(campoId) {
    document.getElementById(campoId).value = Math.floor(Math.random() * 9000000000) + 1000000000;
}

function limparCamposLeitura() {
    window.beepTocado = false;
    window.beepTocado = false;
    ['input-mac', 'input-sn', 'input-imei', 'input-cimi'].forEach(id => {
        let el = document.getElementById(id);
        if(el) {
            el.value = "";
            el.style.backgroundColor = '';
            el.style.borderColor = '';
            el.style.color = '';
        }
    });
}

function forcarLeituraVisual() {
    if (!monitorConnected) {
        showToast("Ligue o Monitor Serial Primeiro!", "warning");
        return;
    }
    socket.emit('analisar_buffer_socket');
    showToast("A extrair dados do buffer...", "success");
}

// --- COMUNICAÇÃO SERIAL (MONITOR & FLASH) ---
async function carregarPortas() {
    try { 
        const res = await fetch('/listar_portas'); 
        const dados = await res.json(); 
        const sel = document.getElementById('selectPorta'); 
        const atual = sel.value; 
        sel.innerHTML = ""; 
        dados.forEach(p => {
            let nome = p.device + " | " + p.description;
            if (p.description.match(/CP210|CH340|Serial|USB/i)) nome = nome + " [ RECOMENDADA ]";
            sel.add(new Option(nome, p.device));
        }); 
        if (atual) sel.value = atual; 
    } catch(e) {}
}

function toggleMonitor() {
    const porta = document.getElementById('selectPorta').value;
    const baud = document.getElementById('monitorBaud').value;
    const btn = document.getElementById('btn-monitor');
    
    if (!monitorConnected) { 
        if (!porta) { showToast("Selecione uma porta primeiro.", "error"); return; }
        socket.emit('iniciar_monitor', { porta, baud }); 
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Ligar...'; 
    } else { 
        socket.emit('parar_monitor'); 
        btn.innerHTML = '<i class="fas fa-plug me-1"></i> Conectar'; 
    }
}

function iniciar(modo) {
    if (monitorConnected) toggleMonitor(); 
    if (activeTab !== 'install') switchConsole('install');
    
    const porta = document.getElementById('selectPorta').value;
    const ficheiro = document.getElementById('selectFicheiro').value;
    const baud = document.getElementById('selectBaud').value;
    
    if (!porta) { showToast("Porta obrigatória!", "error"); return; }
    if (modo === 'flash_limpo' && !ficheiro) { showToast("Tem de selecionar um ficheiro Firmware!", "error"); return; }
    
    document.getElementById('status-text').innerText = "A PROCESSAR..."; 
    document.getElementById('status-text').className = "text-warning fw-bold"; 
    document.getElementById('barra').style.width = "5%"; 
    
    limparCamposLeitura();
    startTimer();
    socket.emit('iniciar_processo', { porta, baud, ficheiro, modo });
}

// --- WEBSOCKETS LISTENERS ---
socket.on('status_monitor', msg => {
    const btn = document.getElementById('btn-monitor'); 
    monitorConnected = msg.ativo;
    
    if (msg.ativo) { 
        btn.innerHTML = '<i class="fas fa-power-off me-1"></i> Desconectar'; 
        btn.className = 'btn btn-sm btn-danger fw-bold'; 
        consola.innerHTML += `<div class='log-line text-info fw-bold'>>> MONITOR LIGADO: ${msg.msg}</div>`; 
    } else { 
        btn.innerHTML = '<i class="fas fa-plug me-1"></i> Conectar'; 
        btn.className = 'btn btn-sm btn-outline-info fw-bold'; 
        consola.innerHTML += `<div class='log-line' style='color: var(--danger);'>>> MONITOR DESLIGADO.</div>`; 
    }
    consola.scrollTop = consola.scrollHeight;
});

socket.on('log_monitor', msg => { 
    if (activeTab === 'monitor') { 
        const div = document.createElement('div'); 
        div.className = 'log-line'; 
        div.innerText = msg.data; 
        consola.appendChild(div); 
        if (consola.childNodes.length > 500) consola.removeChild(consola.firstChild); 
        consola.scrollTop = consola.scrollHeight; 
    } 
});

socket.on('dados_capturados', dados => { 
    let alterou = false;
    if (dados.mac && !document.getElementById('input-mac').value) {
        document.getElementById('input-mac').value = dados.mac.replace(/:/g, '').toLowerCase(); 
        showToast("✓ MAC Address Identificado!", "success");
        alterou = true;
    }
    if (dados.imei && !document.getElementById('input-imei').value) {
        document.getElementById('input-imei').value = dados.imei; 
        showToast("✓ IMEI GSM Extraído!", "success");
        alterou = true;
    }
    if (dados.cimi && !document.getElementById('input-cimi').value) {
        document.getElementById('input-cimi').value = dados.cimi; 
        showToast("✓ CIMI Identificado!", "success");
        alterou = true;
    }
    if (dados.serial && !document.getElementById('input-sn').value) {
        document.getElementById('input-sn').value = dados.serial; 
        alterou = true;
    }
    
    if(alterou) {
        checkInputVisuals();
        const mm = document.getElementById('input-mac');
        const ii = document.getElementById('input-imei');
        const cc = document.getElementById('input-cimi');
        // Se os 3 dados vitais estao preenchidos e o beep ainda nao tocou hoje
        if (mm && ii && cc && mm.value.length > 5 && ii.value.length > 5 && cc.value.length > 5 && !window.beepTocado) {
            if (typeof tocarSomSucesso === 'function') tocarSomSucesso();
            window.beepTocado = true;
        }
    }
});

socket.on('log_flash', msg => {
    if (activeTab === 'install') {
        let cleanData = msg.data.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\x1b\[K/g, ''); 
        if (!cleanData.trim()) return;
        
        const div = document.createElement('div'); 
        div.className = 'log-line';
        
        if (cleanData.includes("✅") || cleanData.includes("SUCESSO")) { div.className += ' log-success'; showToast("Flash Concluído!", "success"); stopTimer(true); }
        if (cleanData.includes("❌") || cleanData.includes("Fatal")) { div.className += ' log-error'; showToast("Erro Crítico no Flash!", "error"); stopTimer(false); }
        
        div.innerText = "> " + cleanData; 
        consola.appendChild(div); 
        consola.scrollTop = consola.scrollHeight;
        
        if (cleanData.includes("Writing")) document.getElementById('barra').style.width = "60%";
        if (cleanData.includes("Verifying")) document.getElementById('barra').style.width = "85%";
    }
});

socket.on('fim_processo', (data) => { 
    document.getElementById('barra').style.width = "100%"; 
    consola.innerHTML += "<div class='log-line text-success fw-bold' style='margin-top: 10px;'>>> PROCESSO TERMINADO!</div>"; 
    consola.scrollTop = consola.scrollHeight; 

    // data.sucesso vem do backend a indicar se o esptool retornou código 0
    if (data && data.sucesso === true) {
        document.getElementById('status-text').innerText = "Concluído"; 
        document.getElementById('status-text').className = "text-success fw-bold"; 
        
        if (isAutoModeRunning) {
            modalResetObj.show();
            const porta = document.getElementById('selectPorta').value;
            socket.emit('iniciar_monitor', { porta: porta, baud: 115200 }); // Liga monitor automaticamente
        }
    } else {
        document.getElementById('status-text').innerText = "Falhou"; 
        document.getElementById('status-text').className = "text-danger fw-bold";
        
        if (isAutoModeRunning) {
            modalErroFlashObj.show(); // MOSTRA MODAL BONITA DE ERRO
            isAutoModeRunning = false;
            resetBotaoAutomacao();
        }
    }
});

// --- AUTOMAÇÃO MES (TUDO-EM-1) ---
function iniciarAutomacaoMES() {
    const ficheiro = document.getElementById('selectFicheiro').value;
    const porta = document.getElementById('selectPorta').value;
    
    if (!porta) { showToast("Selecione uma porta COM!", "warning"); return; }
    if (!ficheiro && !perfilAtivo) { showToast("Selecione um ficheiro ou ative um perfil!", "warning"); return; }
    
    const etiquetaUsar = perfilAtivo ? perfilAtivo.zpl : etiquetaAtiva;
    if (!etiquetaUsar || etiquetaUsar === "") {
        showToast("Falta configurar o Molde ZPL!", "error");
        return;
    }

    isAutoModeRunning = true;
    const btn = document.getElementById('btn-automacao');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin fa-lg me-2"></i> A PROCESSAR...';
    btn.disabled = true;

    consola.innerHTML += `<div class='log-line log-warning'>>> A INICIAR AUTOMAÇÃO DE PRODUÇÃO TUDO-EM-1...</div>`;
    iniciar('flash_limpo'); 
}

function confirmarResetFeito() {
    modalResetObj.hide();
    consola.innerHTML += `<div class='log-line text-warning'>>> AGUARDAR DADOS DA PLACA...</div>`;
    
    const btn = document.getElementById('btn-automacao');
    btn.disabled = false;
    btn.className = "btn btn-success w-100 py-3 mb-4 fw-bold pulse-animation";
    btn.innerHTML = `<i class="fas fa-check-double fa-lg me-2"></i> VALIDAR DADOS LIDOS`;
    btn.onclick = dadosEncontradosAvançar;
}

function dadosEncontradosAvançar() {
    let inMac = document.getElementById('input-mac').value;
    if (!inMac || inMac.length < 5) {
        if(!confirm("Aviso: Ainda não foi lido nenhum MAC Address! Tem a certeza que quer avançar para a impressão?")) return;
    }

    if (monitorConnected) toggleMonitor(); 
    
    document.getElementById('mod-mac').value = document.getElementById('input-mac').value;
    document.getElementById('mod-imei').value = document.getElementById('input-imei').value;
    document.getElementById('mod-cimi').value = document.getElementById('input-cimi').value;
    
    let painelSN = document.getElementById('input-sn').value;
    if (!painelSN) painelSN = Math.floor(Math.random() * 9000000000) + 1000000000;
    document.getElementById('mod-sn').value = painelSN;
    document.getElementById('mod-qtd').value = 1;
    
    modalConfirmObj.show();
}

function cancelarAutomacao() {
    isAutoModeRunning = false;
    limparCamposLeitura();
    resetBotaoAutomacao();
}

function resetBotaoAutomacao() {
    const btn = document.getElementById('btn-automacao');
    btn.disabled = false;
    btn.className = "btn btn-mega w-100 py-3 mb-4 fw-bold";
    btn.innerHTML = `<i class="fas fa-bolt fa-lg me-2"></i> TUDO EM 1<br><span class="small" style="font-weight: 600;">Flash + Lê Logs + ZPL</span>`;
    btn.onclick = iniciarAutomacaoMES; 
}

async function concluirFluxoAutomatico() {
    modalConfirmObj.hide();
    isAutoModeRunning = false;
    
    const payload = {
        mac: document.getElementById('mod-mac').value,
        sn: document.getElementById('mod-sn').value,
        imei: document.getElementById('mod-imei').value,
        cimi: document.getElementById('mod-cimi').value,
        perfil: perfilAtivo ? perfilAtivo.nome : "Manual"
    };
    
    const quantidadeRequerida = document.getElementById('mod-qtd').value;
    const etiquetaUsar = perfilAtivo ? perfilAtivo.zpl : etiquetaAtiva;

    try {
        await fetch('/guardar_csv_manual', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(payload) 
        });
        carregarLogsDoCSV();
        await enviarParaMotorZPL(payload.mac, payload.sn, payload.imei, payload.cimi, etiquetaUsar, quantidadeRequerida);
        consola.innerHTML += `<div class='log-line text-success fw-bold'>>> CICLO MES COMPLETADO COM SUCESSO!</div>`;
    } catch(e) { 
        showToast("Erro Fatal durante gravação: " + e.message, "error"); 
    } finally {
        resetBotaoAutomacao();
        consola.scrollTop = consola.scrollHeight;
    }
}

// --- MÓDULO ZPL ---
async function enviarParaMotorZPL(mac, sn, imei, cimi, label_file, qtd) {
    const ip = document.getElementById('ip-impressora').value.trim();
    
    const resposta = await fetch('/api/processar_zpl_v6', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ mac, imei, sn, cimi, label_file, ip_impressora: ip, quantidade: qtd }) 
    });
    
    const jsonZpl = await resposta.json();
    
    if (jsonZpl.sucesso) {
        if (jsonZpl.impresso_direto) {
            consola.innerHTML += `<div class='log-line log-success'>>> <i class="fas fa-print"></i> ENVIADAS ${qtd} ETIQUETAS (IP: ${ip})!</div>`;
            showToast(`Impressão enviada para ${ip}`, "success");
        } else {
            const blob = new Blob([jsonZpl.zpl], {type:'text/plain'});
            const a = document.createElement('a');
            a.href = window.URL.createObjectURL(blob);
            const extensaoOriginal = label_file ? label_file.split('.').pop() : 'zpl';
            a.download = `Etiquetas_${sn}_x${qtd}.${extensaoOriginal}`;
            a.click();
            consola.innerHTML += `<div class='log-line log-success'>>> <i class="fas fa-download"></i> FICHEIRO DESCARREGADO!</div>`;
            showToast("Ficheiro ZPL Descarregado!", "success");
        }
    } else {
        showToast("Erro no Módulo ZPL", "error");
        consola.innerHTML += `<div class='log-line log-error'>>> ERRO IMPRESSORA: ${jsonZpl.erro}</div>`;
    }
}

// --- MODO OFFLINE ---
async function analisarOffline() {
    const input = document.getElementById('offline-file');
    if (input.files.length === 0) { showToast("Selecione um ficheiro de log .txt!", "warning"); return; }
    
    const fd = new FormData(); 
    fd.append('file', input.files[0]);
    
    try {
        const res = await fetch('/analisar_logs_ficheiro', { method: 'POST', body: fd });
        const dados = await res.json();
        if (dados.erro) { showToast(dados.erro, "error"); return; }
        
        document.getElementById('off-mac').value = dados.mac ? dados.mac.replace(/:/g, '').toLowerCase() : '';
        document.getElementById('off-imei').value = dados.imei || '';
        document.getElementById('off-cimi').value = dados.cimi || '';
        
        if (!document.getElementById('off-sn').value) document.getElementById('off-sn').value = Math.floor(Math.random() * 9000000000) + 1000000000;
        showToast("Logs analisados com sucesso!", "success");
    } catch(e) { showToast("Erro: " + e.message, "error"); }
}

async function processarOfflineCompleto(salvarNoHistorico) {
    const mac = document.getElementById('off-mac').value;
    const sn = document.getElementById('off-sn').value;
    const imei = document.getElementById('off-imei').value;
    const cimi = document.getElementById('off-cimi').value;
    
    if (!mac && !imei && !cimi) { showToast("Sem dados para processar!", "error"); return; }
    
    const etiquetaUsar = perfilAtivo ? perfilAtivo.zpl : etiquetaAtiva;
    if (!etiquetaUsar) { 
        showPanel('painel-etiquetas'); 
        showToast("Ative um Modelo ZPL primeiro!", "warning"); 
        return; 
    }
    
    try {
        if(salvarNoHistorico) {
            await fetch('/guardar_csv_manual', { 
                method: 'POST', headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({ mac, imei, sn, cimi, perfil: 'Offline' }) 
            });
            carregarLogsDoCSV();
        }
        await enviarParaMotorZPL(mac, sn, imei, cimi, etiquetaUsar, 1);
    } catch(e) { showToast("Erro ao processar ZPL", "error"); }
}

// --- GESTÃO DE ARQUIVOS ---
async function carregarArquivos(renderList = true) { 
    const resB = await fetch('/listar_ficheiros?t=' + new Date().getTime()); 
    const bins = await resB.json(); 
    
    const selMain = document.getElementById('selectFicheiro');
    const selPerfil = document.getElementById('p-file');
    
    if(selMain) { const atual = selMain.value; selMain.innerHTML = ""; bins.forEach(f => selMain.add(new Option(f, f))); if(atual) selMain.value = atual; }
    if(selPerfil) { selPerfil.innerHTML = ""; bins.forEach(f => selPerfil.add(new Option(f, f))); }
    
    if (renderList) { 
        const lista = document.getElementById('listaFiles'); lista.innerHTML = ""; 
        bins.forEach(f => { lista.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center" style="background:transparent;"><span><i class="fas fa-file-code me-2 text-primary"></i>${f}</span><button class="btn btn-sm btn-outline-danger admin-only" onclick="apagarArquivo('${f}', 'bin')"><i class="fas fa-trash"></i></button></li>`; }); 
    } 
}

async function carregarEtiquetas() {
    const resZ = await fetch('/listar_etiquetas?t=' + new Date().getTime()); 
    const zpls = await resZ.json();
    
    const selZpl = document.getElementById('p-zpl');
    if(selZpl) { selZpl.innerHTML = "<option value=''>Nenhuma</option>"; zpls.forEach(f => selZpl.add(new Option(f, f))); }

    const lista = document.getElementById('listaEtiquetas'); lista.innerHTML = "";
    if (zpls.length === 0) { lista.innerHTML = "<li class='list-group-item text-muted' style='background:transparent;'>Vazio.</li>"; atualizarBadges();
    aplicarEstadoPreferencias(); return; }
    
    zpls.forEach(f => {
        const isAtiva = (f === etiquetaAtiva);
        lista.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center ${isAtiva ? 'bg-light' : ''}" style="background:transparent; border-left: ${isAtiva ? '4px solid var(--accent)' : '1px solid var(--border)'};">
            <span><i class="fas fa-tag me-2 ${isAtiva ? 'text-primary' : 'text-muted'}"></i><strong class="${isAtiva ? 'text-primary' : ''}">${f}</strong></span>
            <div><button class="btn btn-sm ${isAtiva ? 'btn-success' : 'btn-outline-primary'} me-2 fw-bold" onclick="ativarEtiquetaManual('${f}')">${isAtiva ? '<i class="fas fa-check"></i>' : 'Usar'}</button><button class="btn btn-sm btn-outline-danger admin-only" onclick="apagarArquivo('${f}', 'zpl')"><i class="fas fa-trash"></i></button></div>
        </li>`;
    });
    atualizarBadges();
    aplicarEstadoPreferencias();
}

async function uploadArquivo(inputId, urlRota) { 
    const input = document.getElementById(inputId); 
    if (!input || input.files.length === 0) {
        showToast("Selecione um ficheiro primeiro!", "warning");
        return; 
    }
    const fd = new FormData(); 
    fd.append('file', input.files[0]); 
    try {
        const res = await fetch(urlRota, { method: 'POST', body: fd }); 
        if (res.ok) { 
            const jsonResposta = await res.json();
            input.value = ""; 
            if (jsonResposta.sucesso) {
                showToast("Upload Concluído com sucesso!", "success");
                // Forçar recarregamento das listas sem precisar de F5
                if (urlRota.includes('etiqueta')) {
                    carregarEtiquetas();
                } else {
                    carregarArquivos();
                }
            } else {
                showToast(jsonResposta.erro || "Erro no Upload.", "error");
            }
        } else {
            showToast("Falha na comunicação com o servidor", "error");
        }
    } catch (e) {
        showToast("Erro: " + e.message, "error");
    }
}

function abrirModal(id) {
    const m = document.getElementById(id);
    if (m) {
        let modal = bootstrap.Modal.getInstance(m);
        if (!modal) modal = new bootstrap.Modal(m);
        modal.show();
    }
}

async function apagarArquivo(nome, tipo) { 
    if (!confirm(`Apagar permanentemente "${nome}"?`)) return;
    const rota = tipo === 'zpl' ? '/delete_etiqueta' : '/delete_file';
    await fetch(rota, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({filename: nome}) }); 
    if (tipo === 'zpl') { if (etiquetaAtiva === nome) { etiquetaAtiva = null; localStorage.removeItem('etiquetaAtiva'); } carregarEtiquetas(); } 
    else { carregarArquivos(); }
    showToast("Ficheiro apagado.", "success");
}

// --- GESTÃO DE PERFIS (COM ESTADO VAZIO) ---
async function carregarDadosPerfis() {
    await carregarArquivos(false); await carregarEtiquetas(); 
    const res = await fetch('/api/perfis?t=' + new Date().getTime()); 
    perfisList = await res.json();
    const container = document.getElementById('grid-perfis'); 
    container.innerHTML = "";
    
    if (perfisList.length === 0) { 
        container.innerHTML = `
        <div class='col-12 text-center py-5 mt-4' style='border: 2px dashed var(--border); border-radius: 12px; background: rgba(255,255,255,0.01);'>
            <i class='fas fa-id-card-alt fa-3x mb-3' style='color: var(--border);'></i>
            <h5 class='text-muted fw-bold'>Nenhum Perfil de Produção Configurado</h5>
            <p class='small text-muted'>Aceda ao menu de Definições, introduza a password de Administrador para desbloquear o sistema e crie os perfis obrigatórios.</p>
        </div>`; 
        return; 
    }

    perfisList.forEach(p => {
        let btns = `<button class="btn btn-sm btn-primary fw-bold" onclick='ativarPerfil(${JSON.stringify(p)})'>Usar Perfil</button>`;
        if(p.pdf) btns += `<a class="btn btn-sm btn-outline-info fw-bold ms-2" href="/download_pdf/${p.pdf}" target="_blank"><i class="fas fa-file-pdf"></i> Manual</a>`;
        let btnDelete = isAdmin ? `<button class="btn btn-sm btn-outline-danger ms-auto" onclick="apagarPerfil(${p.id})"><i class="fas fa-trash"></i></button>` : '';
        
        container.innerHTML += `
        <div class="col-md-4 mb-4">
            <div class="custom-card h-100 mb-0 d-flex flex-column" style="background: rgba(255,255,255,0.02);">
                <h5 class="fw-bold text-primary border-bottom pb-2" style="border-color: var(--border) !important;">${p.nome}</h5>
                <div class="small text-muted mb-3 flex-grow-1 mt-2">
                    <div class="mb-2"><i class="fas fa-microchip me-2" style="color: var(--accent);"></i>${p.file}</div>
                    <div class="mb-2"><i class="fas fa-tachometer-alt me-2" style="color: var(--warning);"></i>${p.baud} Baud</div>
                    <div class="mb-2"><i class="fas fa-tag me-2" style="color: var(--success);"></i>${p.zpl || '<span class="text-danger">Sem ZPL Atribuída</span>'}</div>
                </div>
                <div class="d-flex align-items-center mt-auto pt-3 border-top" style="border-color: var(--border) !important;">
                    ${btns}${btnDelete}
                </div>
            </div>
        </div>`;
    });
}

async function salvarPerfil() {
    const nome = document.getElementById('p-nome').value;
    const file = document.getElementById('p-file').value;
    const baud = document.getElementById('p-baud').value;
    const zpl = document.getElementById('p-zpl').value;
    const pdfInput = document.getElementById('p-pdf');
    let pdfName = "";

    if (!nome || !file) { showToast("Nome e Firmware são obrigatórios.", "error"); return; } 

    if(pdfInput.files.length > 0) {
        const fd = new FormData(); fd.append('file', pdfInput.files[0]);
        const r = await fetch('/upload_pdf', {method:'POST', body:fd});
        if(r.ok) pdfName = pdfInput.files[0].name; 
    }
    
    perfisList.push({ id: Date.now(), nome, file, baud, zpl, pdf: pdfName });
    await fetch('/api/perfis', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(perfisList) });
    
    document.getElementById('p-nome').value = ""; document.getElementById('p-pdf').value = "";
    showToast("Perfil gravado com sucesso!", "success");
    carregarDadosPerfis();
}

async function apagarPerfil(id) { 
    if (!confirm("Eliminar Perfil?")) return; 
    perfisList = perfisList.filter(p => p.id !== id); 
    await fetch('/api/perfis', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(perfisList) }); 
    carregarDadosPerfis(); 
    if(perfilAtivo && perfilAtivo.id === id) cancelarPerfil();
}

function ativarPerfil(p) {
    perfilAtivo = p; 
    document.getElementById('selectFicheiro').value = p.file; 
    document.getElementById('selectBaud').value = p.baud;
    document.getElementById('selectFicheiro').disabled = true; 
    document.getElementById('selectBaud').disabled = true; 
    atualizarBadges();
    aplicarEstadoPreferencias(); showPanel('painel-flash');
    showToast(`Perfil ${p.nome} Ativado.`, "success");
}

function cancelarPerfil() {
    perfilAtivo = null; 
    document.getElementById('selectFicheiro').disabled = false; 
    document.getElementById('selectBaud').disabled = false; 
    atualizarBadges();
    aplicarEstadoPreferencias();
}

function ativarEtiquetaManual(nome) { 
    if(perfilAtivo) { showToast("Cancele o perfil para usar ZPL manual livre.", "warning"); return; }
    etiquetaAtiva = nome; localStorage.setItem('etiquetaAtiva', nome); 
    carregarEtiquetas(); 
}

function atualizarBadges() {
    const lblBadge = document.getElementById('label-name');
    const prfBadge = document.getElementById('perfil-name');
    if(lblBadge) lblBadge.innerText = perfilAtivo ? (perfilAtivo.zpl || "Nenhuma") : (etiquetaAtiva || "Nenhuma");
    if(prfBadge) prfBadge.innerHTML = perfilAtivo ? `${perfilAtivo.nome}` : "Manual Livre";
}

// --- HISTÓRICO CSV ---
async function carregarLogsDoCSV() { 
    try {
        const res = await fetch('/api/logs?t=' + new Date().getTime()); 
        logHistory = await res.json(); renderizarTabelaLogs();
    } catch(e) {}
}

function renderizarTabelaLogs() {
    const tbody = document.getElementById('table-logs-body'); 
    if (logHistory.length === 0) { tbody.innerHTML = "<tr><td colspan='7' class='text-center text-muted py-4'>Sem registos de produção.</td></tr>"; return; } 
    
    const dataF = document.getElementById('filtro-data').value;
    const perfF = document.getElementById('filtro-perfil').value.toLowerCase();
    const fwF = document.getElementById('filtro-fw').value.toLowerCase();
    
    tbody.innerHTML = ""; 
    let renderizados = 0;
    
    logHistory.forEach((l, originalIndex) => {
        if(dataF && !l.Data.includes(dataF)) return;
        let nomePerfil = l.Perfil || "N/A";
        if(perfF && !nomePerfil.toLowerCase().includes(perfF)) return;
        if(fwF && !l.Firmware.toLowerCase().includes(fwF)) return;
        
        renderizados++;
        let btnApagar = `<button class="btn btn-sm btn-outline-danger" onclick="apagarLinhaUnicaCSV(${originalIndex})"><i class="fas fa-trash"></i></button>`;
        tbody.innerHTML = `<tr><td>${l.Data}</td><td class="font-monospace text-primary">${l.MAC}</td><td class="font-monospace text-warning">${l.Serial || '-'}</td><td>${l.IMEI}</td><td class="text-danger">${l.CIMI || '-'}</td><td>${nomePerfil}</td><td class="admin-only-cell">${btnApagar}</td></tr>` + tbody.innerHTML;
    });
}

async function apagarTudoCSV() { 
    if (confirm("PERIGO: Destruir TODO o Histórico de Produção?")) { 
        await fetch('/api/delete_csv', { method: 'POST' }); 
        carregarLogsDoCSV(); 
        showToast("Histórico apagado.", "success");
    } 
}

async function apagarLinhaUnicaCSV(indexOriginal) { 
    if(confirm("Apagar registo desta placa?")) { 
        await fetch('/api/delete_csv_row', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ index: indexOriginal }) }); 
        carregarLogsDoCSV(); 
    } 
}

// --- ENCERRAMENTO ---
function fecharAplicacao() { 
    if (confirm("Deseja desligar o servidor do Flasher?")) { 
        fetch('/shutdown', { method: 'POST' }); 
        document.body.innerHTML = `<div class='shutdown-screen'><i class="fas fa-power-off fa-4x mb-4" style="color: var(--danger);"></i><h2 class="fw-bold">Sistema Encerrado</h2><p class="text-muted mt-2">Pode fechar a janela em segurança.</p></div>`; 
        setTimeout(() => window.close(), 2000); 
    } 
}

// --- PREFERÊNCIAS E SOM (BEEP) ---
function aplicarEstadoPreferencias() {
    const tutAtivos = localStorage.getItem('tutoriaisAtivos') !== 'false';
    document.querySelectorAll('.btn-tutorial').forEach(btn => {
        btn.style.setProperty('display', tutAtivos ? 'inline-block' : 'none', 'important');
    });
    const tTut = document.getElementById('toggle-tutoriais');
    if (tTut) tTut.checked = tutAtivos;
    
    const somAtivo = localStorage.getItem('somAtivo') !== 'false';
    const tSom = document.getElementById('toggle-som');
    if (tSom) tSom.checked = somAtivo;
}

function alternarTutoriais() {
    localStorage.setItem('tutoriaisAtivos', document.getElementById('toggle-tutoriais').checked);
    aplicarEstadoPreferencias();
}

function alternarSom() {
    localStorage.setItem('somAtivo', document.getElementById('toggle-som').checked);
}

function tocarSomSucesso() {
    if (localStorage.getItem('somAtivo') === 'false') return;
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        
        // Primeiro tom (Agudo)
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.connect(gain1); gain1.connect(ctx.destination);
        osc1.type = 'sine'; osc1.frequency.setValueAtTime(880, ctx.currentTime); // Nota A5
        gain1.gain.setValueAtTime(0.1, ctx.currentTime);
        osc1.start(); osc1.stop(ctx.currentTime + 0.15);
        
        // Segundo tom (Mais Agudo, confirmacao)
        setTimeout(() => {
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.connect(gain2); gain2.connect(ctx.destination);
            osc2.type = 'sine'; osc2.frequency.setValueAtTime(1108.73, ctx.currentTime); // Nota C#6
            gain2.gain.setValueAtTime(0.1, ctx.currentTime);
            osc2.start(); osc2.stop(ctx.currentTime + 0.3);
        }, 150);
    } catch(e) { console.warn("Áudio não suportado ou bloqueado no navegador."); }
}
