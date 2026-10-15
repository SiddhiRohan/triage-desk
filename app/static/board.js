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
        
        // Priority weight for sorting: high=3, normal=2, low=1
        const priorityWeight = { high: 3, normal: 2, low: 1 };
        
        // Initialize counts and containers for each queue
        const queueNames = ['Support', 'Billing', 'Bug', 'Sales', 'General', 'Needs human'];
        const counts = {};
        queueNames.forEach(name => { counts[name] = 0; });
        
        const queues = {
            'Support': document.querySelector('[data-queue="Support"] .cards'),
            'Billing': document.querySelector('[data-queue="Billing"] .cards'),
            'Bug': document.querySelector('[data-queue="Bug"] .cards'),
            'Sales': document.querySelector('[data-queue="Sales"] .cards'),
            'General': document.querySelector('[data-queue="General"] .cards'),
            'Needs human': document.querySelector('[data-queue="Needs human"] .cards')
        };
        
        // Group messages by queue, preserving original index for stable sort
        const queueMessages = {};
        queueNames.forEach(name => { queueMessages[name] = []; });
        messages.forEach((msg, index) => {
            const q = msg.queue || 'General';
            if (!queueMessages[q]) {
                queueMessages[q] = [];
            }
            queueMessages[q].push({ msg, index });
        });
        
        // For each queue, sort by priority weight descending, then by original index ascending
        queueNames.forEach(queueName => {
            const msgs = queueMessages[queueName];
            if (!msgs) return;
            
            msgs.sort((a, b) => {
                const weightA = priorityWeight[a.msg.priority] || 0;
                const weightB = priorityWeight[b.msg.priority] || 0;
                if (weightA !== weightB) {
                    return weightB - weightA; // descending weight
                }
                return a.index - b.index; // stable: original order
            });
            
            // Update count
            counts[queueName] = msgs.length;
            
            const container = queues[queueName];
            msgs.forEach(({ msg }) => {
                const q = msg.queue || 'General';
                const card = document.createElement('div');
                card.className = 'card';
                if (q === 'Needs human') card.classList.add('needs-human');
                
                const priorityClass = `priority-${msg.priority.toLowerCase()}`;
                const badgePriorityClass = `badge-priority-${msg.priority.toLowerCase()}`;
                
                // Add priority class to card for left border color
                card.classList.add(priorityClass);
                
                card.innerHTML = `
                    ${q === 'Needs human' ? '<span class="badge badge-human">HUMAN REQUIRED</span>' : ''}
                    <h3>${msg.subject}</h3>
                    <div class="meta">
                        <span class="badge">${msg.category}</span>
                        <span class="${badgePriorityClass}">${msg.priority}</span>
                        <span>Conf: ${msg.confidence.toFixed(2)}</span>
                    </div>
                `;
                
                card.onclick = () => showDetail(msg.id);
                container.appendChild(card);
            });
        });
        
        // Update queue headers with counts
        updateQueueHeaders(counts);
    } catch (e) {
        console.error('Error loading messages:', e);
    }
}

function updateQueueHeaders(counts) {
    const queueNames = ['Support', 'Billing', 'Bug', 'Sales', 'General', 'Needs human'];
    queueNames.forEach(name => {
        const headerEl = document.querySelector(`[data-queue="${name}"] h2`);
        if (headerEl) {
            headerEl.textContent = `${name} (${counts[name] || 0})`;
        }
    });
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