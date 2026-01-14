let currentSymbol = null;
let currentChart = null;
let compareChartInstance = null;
let priceData = [];
let predictionData = null;
const DAYS_DEFAULT = 90;
const API_BASE = 'http://127.0.0.1:8000/api/v1';

document.addEventListener('DOMContentLoaded', async () => {
    try {
        await loadCompanies();
        document.getElementById('dashboard-content').style.display = 'block';
        document.getElementById('dashboard-content').style.opacity = '1';
    } catch (err) {
        console.error('Initialization failed:', err);
    }
});

async function loadCompanies() {
    const res = await fetch(`${API_BASE}/companies`);
    const companies = await res.json();
    const listEl = document.getElementById('company-list');

    listEl.innerHTML = companies.map(c => `
        <div class="company-item" onclick="selectCompany('${c.symbol}')" id="item-${c.symbol}">
            <div class="company-info">
                <span class="symbol">${c.symbol.replace('.NS', '')}</span>
                <span class="name">${c.name}</span>
            </div>
            <div class="active-indicator"></div>
        </div>
    `).join('');

    if (companies.length > 0) {
        selectCompany(companies[0].symbol);
    }
}

async function selectCompany(symbol) {
    if (currentSymbol === symbol) return;
    currentSymbol = symbol;

    document.querySelectorAll('.company-item').forEach(el => el.classList.remove('active'));
    document.getElementById(`item-${symbol}`).classList.add('active');

    const contentInfo = document.querySelector('.stock-header');
    const chartArea = document.querySelector('.chart-container');
    const analytics = document.querySelector('.analytics-col');

    if (contentInfo) contentInfo.style.opacity = '0.6';
    if (chartArea) chartArea.style.opacity = '0.6';
    if (analytics) analytics.style.opacity = '0.6';

    try {
        const [prices, summary, analyticsData, prediction, sentiment] = await Promise.all([
            fetch(`${API_BASE}/data/${symbol}?days=180`).then(r => r.json()),
            fetch(`${API_BASE}/summary/${symbol}`).then(r => r.json()),
            fetch(`${API_BASE}/analytics/${symbol}`).then(r => r.json()),
            fetch(`${API_BASE}/prediction/${symbol}`).then(r => r.json()).catch(() => null),
            fetch(`${API_BASE}/sentiment/${symbol}`).then(r => r.json()).catch(() => null)
        ]);

        priceData = prices;
        predictionData = prediction;

        updateHeader(summary);
        updateAnalytics(analyticsData);
        updateSentiment(sentiment);
        updatePrediction(prediction);
        updateChart(DAYS_DEFAULT);

    } catch (err) {
        console.error('Data load failed:', err);
    } finally {
        if (contentInfo) contentInfo.style.opacity = '1';
        if (chartArea) chartArea.style.opacity = '1';
        if (analytics) analytics.style.opacity = '1';

        document.getElementById('loading-overlay').style.display = 'none';
        document.getElementById('dashboard-content').style.display = 'block';
    }
}

function updateHeader(summary) {
    animateValue('stock-price', summary.current_price);

    const symbolEl = document.getElementById('stock-symbol');
    const nameEl = document.getElementById('stock-name');

    symbolEl.textContent = summary.symbol.replace('.NS', '');
    nameEl.textContent = summary.name;

    const changeBadge = document.getElementById('stock-change-badge');
    const isPos = summary.change_52w_pct >= 0;

    changeBadge.style.transition = 'opacity 0.2s';
    changeBadge.style.opacity = '0';

    setTimeout(() => {
        changeBadge.textContent = `${isPos ? '+' : ''}${summary.change_52w_pct.toFixed(2)}% (1Y)`;
        changeBadge.style.background = isPos ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';
        changeBadge.style.color = isPos ? '#10b981' : '#ef4444';
        changeBadge.style.opacity = '1';
    }, 200);

    document.getElementById('stock-high').textContent = summary.high_52w.toLocaleString('en-IN');
    document.getElementById('stock-low').textContent = summary.low_52w.toLocaleString('en-IN');

    const range = summary.high_52w - summary.low_52w;
    const progress = Math.min(Math.max(((summary.current_price - summary.low_52w) / range) * 100, 0), 100);
    const fillEl = document.getElementById('price-range-fill');
    fillEl.style.transition = 'width 0.8s ease-out';
    fillEl.style.width = `${progress}%`;
}

function animateValue(id, end) {
    const el = document.getElementById(id);
    const startText = el.textContent.replace(/,/g, '').replace('₹', '');
    const start = parseFloat(startText) || end;

    if (Math.abs(start - end) < 0.01) {
        el.textContent = end.toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
        return;
    }

    const duration = 600;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 4);
        const current = start + (end - start) * ease;
        el.textContent = current.toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    requestAnimationFrame(update);
}

function updateAnalytics(data) {
    document.getElementById('rsi-value').textContent = data.rsi_14?.toFixed(1) || '--';
    document.getElementById('rsi-status').textContent = data.rsi_interpretation;

    const rsiMarker = document.getElementById('rsi-marker');
    rsiMarker.style.transition = 'left 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
    rsiMarker.style.left = `${data.rsi_14 || 50}%`;

    document.getElementById('volatility-value').textContent = `${((data.volatility_20d || 0) * 100).toFixed(1)}%`;
    const vBadge = document.getElementById('volatility-badge');
    vBadge.textContent = `${data.volatility_level} Risk`.toUpperCase();

    document.getElementById('ma7-value').textContent = data.ma_7?.toFixed(1) || '--';
    document.getElementById('ma20-value').textContent = data.ma_20?.toFixed(1) || '--';

    updateSignal('ma7', data.ma_7, data.close);
    updateSignal('ma20', data.ma_20, data.close);
}

function updateSignal(id, maVal, close) {
    const el = document.getElementById(`${id}-signal`);
    if (!maVal) {
        el.textContent = '--';
        return;
    }
    const isAbove = close > maVal;
    const newText = isAbove ? 'BULLISH' : 'BEARISH';

    if (el.textContent !== newText) {
        el.style.transition = 'opacity 0.2s';
        el.style.opacity = '0';
        setTimeout(() => {
            el.textContent = newText;
            el.style.color = isAbove ? '#10b981' : '#ef4444';
            el.style.opacity = '1';
        }, 200);
    }
}

function updateChart(days) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    const data = priceData.slice(-days);
    const labels = data.map(d => new Date(d.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }));
    const prices = data.map(d => d.close);
    const ma20 = data.map(d => d.ma_20);
    const ma7 = data.map(d => d.ma_7);

    if (!currentChart) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(48, 52, 63, 0.1)');
        gradient.addColorStop(1, 'rgba(48, 52, 63, 0)');

        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Price',
                        data: prices,
                        borderColor: '#0a0908',
                        backgroundColor: gradient,
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 0,
                        fill: true,
                        order: 1
                    },
                    {
                        label: 'MA 7',
                        data: ma7,
                        borderColor: '#3b82f6',
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: false,
                        order: 2
                    },
                    {
                        label: 'MA 20',
                        data: ma20,
                        borderColor: '#f59e0b',
                        borderWidth: 1.5,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        tension: 0.3,
                        fill: false,
                        order: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 750,
                    easing: 'easeOutQuart'
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            boxWidth: 10,
                            usePointStyle: true,
                            pointStyle: 'line',
                            font: { size: 10, family: 'Inter' }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        titleColor: '#0a0908',
                        bodyColor: '#30343f',
                        borderColor: '#eae0d5',
                        borderWidth: 1,
                        displayColors: true,
                        padding: 10
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 10 }
                        }
                    },
                    y: {
                        grid: { color: '#f1f5f9' },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 10 }
                        }
                    }
                }
            }
        });
    } else {
        currentChart.data.labels = labels;
        currentChart.data.datasets[0].data = prices;
        currentChart.data.datasets[1].data = ma7;
        currentChart.data.datasets[2].data = ma20;
        currentChart.update('active');
    }
}

window.updateTimeRange = (days) => {
    document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    updateChart(days);
};

function updateSentiment(data) {
    if (!data) return;

    const valueEl = document.getElementById('sentiment-value');
    const barEl = document.getElementById('sentiment-bar');
    const labelEl = document.getElementById('sentiment-label');

    valueEl.textContent = data.sentiment_score?.toFixed(1) || '--';
    barEl.style.width = `${data.sentiment_score || 50}%`;

    labelEl.textContent = data.label || '--';
    labelEl.className = 'badge';

    switch (data.interpretation) {
        case 'strong_bullish':
            labelEl.classList.add('strong-bullish');
            break;
        case 'bullish':
            labelEl.classList.add('bullish');
            break;
        case 'bearish':
            labelEl.classList.add('bearish');
            break;
        case 'strong_bearish':
            labelEl.classList.add('strong-bearish');
            break;
        default:
            labelEl.classList.add('neutral');
    }
}

function updatePrediction(data) {
    if (!data) return;

    const trendEl = document.getElementById('prediction-trend');
    const confEl = document.getElementById('prediction-confidence');

    const trend = data.trend || 'neutral';
    const trendIcon = trend === 'bullish' ? '↑' : trend === 'bearish' ? '↓' : '→';
    trendEl.textContent = `${trendIcon} ${trend.toUpperCase()}`;
    trendEl.className = 'mono-value';
    trendEl.classList.add(trend === 'bullish' ? 'prediction-trend-up' : trend === 'bearish' ? 'prediction-trend-down' : '');

    confEl.textContent = `Confidence: ${data.confidence?.toFixed(1) || '--'}%`;
}

let companiesCache = [];

function openCompareModal() {
    const modal = document.getElementById('compare-modal');
    modal.style.display = 'flex';

    if (companiesCache.length === 0) {
        fetch(`${API_BASE}/companies`)
            .then(r => r.json())
            .then(companies => {
                companiesCache = companies;
                populateCompareDropdowns();
            });
    } else {
        populateCompareDropdowns();
    }
}

function populateCompareDropdowns() {
    const select1 = document.getElementById('compare-stock1');
    const select2 = document.getElementById('compare-stock2');

    const options = companiesCache.map(c =>
        `<option value="${c.symbol}">${c.symbol.replace('.NS', '')} - ${c.name}</option>`
    ).join('');

    select1.innerHTML = options;
    select2.innerHTML = options;

    if (companiesCache.length > 1) {
        select2.selectedIndex = 1;
    }
}

function closeCompareModal() {
    document.getElementById('compare-modal').style.display = 'none';
    document.getElementById('compare-results').style.display = 'none';
}

async function runComparison() {
    const symbol1 = document.getElementById('compare-stock1').value;
    const symbol2 = document.getElementById('compare-stock2').value;

    if (symbol1 === symbol2) {
        alert('Please select two different stocks');
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/compare?symbol1=${symbol1}&symbol2=${symbol2}`);
        const data = await res.json();
        displayComparisonResults(data);
    } catch (err) {
        console.error('Comparison failed:', err);
    }
}

function displayComparisonResults(data) {
    const resultsDiv = document.getElementById('compare-results');
    resultsDiv.style.display = 'block';

    document.getElementById('compare-card-1').innerHTML = `
        <h4>${data.stock1.symbol.replace('.NS', '')}</h4>
        <div class="stat"><span class="stat-label">Price</span><span class="stat-value">₹${data.stock1.current_price.toLocaleString('en-IN')}</span></div>
        <div class="stat"><span class="stat-label">52W High</span><span class="stat-value">₹${data.stock1.high_52w.toLocaleString('en-IN')}</span></div>
        <div class="stat"><span class="stat-label">52W Low</span><span class="stat-value">₹${data.stock1.low_52w.toLocaleString('en-IN')}</span></div>
        <div class="stat"><span class="stat-label">Volatility</span><span class="stat-value">${((data.stock1.volatility || 0) * 100).toFixed(1)}%</span></div>
    `;

    document.getElementById('compare-card-2').innerHTML = `
        <h4>${data.stock2.symbol.replace('.NS', '')}</h4>
        <div class="stat"><span class="stat-label">Price</span><span class="stat-value">₹${data.stock2.current_price.toLocaleString('en-IN')}</span></div>
        <div class="stat"><span class="stat-label">52W High</span><span class="stat-value">₹${data.stock2.high_52w.toLocaleString('en-IN')}</span></div>
        <div class="stat"><span class="stat-label">52W Low</span><span class="stat-value">₹${data.stock2.low_52w.toLocaleString('en-IN')}</span></div>
        <div class="stat"><span class="stat-label">Volatility</span><span class="stat-value">${((data.stock2.volatility || 0) * 100).toFixed(1)}%</span></div>
    `;

    document.getElementById('compare-correlation').textContent = data.correlation?.toFixed(3) || '--';
    document.getElementById('compare-vol-ratio').textContent = data.volatility_ratio?.toFixed(3) || '--';
}

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        closeCompareModal();
    }
});

async function startVisualization() {
    const symbol1 = document.getElementById('compare-stock1').value;
    const symbol2 = document.getElementById('compare-stock2').value;

    closeCompareModal();

    await selectCompany(symbol1);

    const compareCard = document.getElementById('compare-chart-card');
    compareCard.style.display = 'block';

    document.getElementById('compare-chart-title').textContent = `${symbol2.replace('.NS', '')} Performance`;

    try {
        const prices = await fetch(`${API_BASE}/data/${symbol2}?days=180`).then(r => r.json());
        renderCompareChart(prices, 90);

        document.getElementById('main-chart-card').scrollIntoView({ behavior: 'smooth' });

    } catch (err) {
        console.error('Failed to load comparison data:', err);
    }
}

function renderCompareChart(data, days) {
    const ctx = document.getElementById('compareChart').getContext('2d');
    const recentData = data.slice(-days);

    const labels = recentData.map(d => new Date(d.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }));
    const prices = recentData.map(d => d.close);
    const ma20 = recentData.map(d => d.ma_20);

    if (compareChartInstance) {
        compareChartInstance.destroy();
    }

    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.1)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');

    compareChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Price',
                    data: prices,
                    borderColor: '#0a0908',
                    backgroundColor: gradient,
                    borderWidth: 2,
                    tension: 0.3,
                    pointRadius: 0,
                    fill: true
                },
                {
                    label: 'MA 20',
                    data: ma20,
                    borderColor: '#f59e0b',
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: '#0a0908',
                    bodyColor: '#30343f',
                    borderColor: '#eae0d5',
                    borderWidth: 1,
                    displayColors: true,
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                },
                y: {
                    grid: { color: '#f1f5f9' },
                    ticks: { color: '#94a3b8', font: { size: 10 } }
                }
            }
        }
    });
}

function closeComparison() {
    document.getElementById('compare-chart-card').style.display = 'none';
    if (compareChartInstance) {
        compareChartInstance.destroy();
        compareChartInstance = null;
    }
}
