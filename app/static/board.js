let configData = null;
let messagesCount = 0;

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        configData = await res.json();
    } catch (e) {
        console.error('Error loading config:', e);
    }
}

async function loadMessages() {
    try {
        const res = await fetch('/api/messages');
        const messages = await res.json();
        messagesCount = messages.length;
        
        const queues = {
            'Support': document.querySelector('[data-queue="Support"] .cards'),
            'Billing': document.querySelector('[data-queue="Billing"] .cards'),
            'Bug': document.querySelector('[data-queue="Bug"] .cards'),
            'Sales': document.querySelector('[data-queue="Sales"] .cards'),
            'General': document.querySelector('[data-queue="General"] .cards'),
            'Needs human': document.querySelector('[data-queue="Needs human"] .cards')
        };

        messages.forEach(msg => {
            const q = msg.queue || 'General';
            const container = queues[q] || queues['General'];
            
            const card = document.createElement('div');
            card.className = 'card';
            if (q === 'Needs human') card.classList.add('needs-human');
            
            const priorityClass = `priority-${msg.priority.toLowerCase()}`;
            
            card.innerHTML = `
                ${q === 'Needs human' ? '<span class="badge badge-human">HUMAN REQUIRED</span>' : ''}
                <h3>${msg.subject}</h3>
                <div class="meta">
                    <span class="badge">${msg.category}</span>
                    <span class="badge ${priorityClass}">${msg.priority}</span>
                    <span>Conf: ${msg.confidence.toFixed(2)}</span>
                </div>
            `;
            
            card.onclick = () => showDetail(msg.id);
            container.appendChild(card);
        });
    } catch (e) {
        console.error('Error loading messages:', e);
    }
}

async function updateHeader() {
    const header = document.getElementById('config');
    if (configData) {
        header.textContent = `Model: ${configData.model_name} | Threshold: ${configData.confidence_threshold} | Total messages: ${messagesCount}`;
    } else {
        header.textContent = 'Loading config...';
    }
}

async function showDetail(id) {
    try {
        const res = await fetch(`/api/messages/${id}`);
        const msg = await res.json();
        
        const content = document.getElementById('panel-content');
        content.innerHTML = `
            <div class="panel-section">
                <h4>Subject</h4>
                <p><strong>${msg.subject}</strong></p>
            </div>
            <div class="panel-section">
                <h4>Body</h4>
                <p>${msg.body}</p>
            </div>
            <div class="panel-section">
                <h4>Decision</h4>
                <p>Category: ${msg.category}<br>
                   Priority: ${msg.priority}<br>
                   Confidence: ${msg.confidence.toFixed(2)}<br>
                   Reason: ${msg.reason}<br>
                   Source: ${msg.source}<br>
                   Model: ${msg.model}<br>
                   Decided at: ${msg.decided_at}</p>
            </div>
            <div class="panel-section">
                <h4>Audit Trail</h4>
                <div class="audit-trail">
                    ${msg.audit.map(a => `
                        <div class="audit-row">
                            <strong>${a.at}</strong>: ${a.action} - ${a.detail}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        document.getElementById('panel').classList.add('open');
    } catch (e) {
        alert('Error loading details');
    }
}

document.getElementById('panel-close').onclick = () => {
    document.getElementById('panel').classList.remove('open');
};

window.onload = async () => {
    await loadConfig();
    await loadMessages();
    updateHeader();
};
