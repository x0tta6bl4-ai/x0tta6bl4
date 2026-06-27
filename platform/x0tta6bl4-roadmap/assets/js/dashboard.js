async function loadData() {
  const res = await fetch('assets/data/metrics.json');
  const data = await res.json();
  document.querySelector('#last-updated span').textContent = new Date(data.generated_at).toLocaleString();
  buildTimeline(data.timeline);
  buildBudget(data.budget);
  buildTeam(data.team);
  buildCriteria(data.success_criteria);
  updateVoteStatus(data.vote_status);
}
function buildTimeline(timeline) {
  new Chart(document.getElementById('timelineChart'), {
    type: 'bar',
    data: { labels: timeline.map(p=>p.label), datasets: [{ label: 'Weeks', data: timeline.map(p=>p.weeks), backgroundColor:'#3b82f6' }]},
    options: { plugins:{legend:{display:false}}, responsive:true, scales:{y:{beginAtZero:true}} }
  });
}
function buildBudget(budget) {
  new Chart(document.getElementById('budgetChart'), {
    type: 'doughnut',
    data: { labels: budget.items.map(i=>i.name), datasets: [{ data: budget.items.map(i=>i.amount), backgroundColor:['#6366f1','#10b981','#f59e0b','#ef4444','#3b82f6'] }]},
    options: { plugins:{legend:{position:'bottom'}}, cutout:'55%' }
  });
}
function buildTeam(team) {
  new Chart(document.getElementById('teamChart'), {
    type: 'bar',
    data: { labels: team.roles.map(r=>r.role), datasets: [{ label:'FTE', data: team.roles.map(r=>r.fte), backgroundColor:'#10b981' }]},
    options: { plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true, precision:0}} }
  });
}
function buildCriteria(criteria) {
  const ul = document.getElementById('successCriteria');
  ul.innerHTML = '';
  criteria.forEach(c => { const li = document.createElement('li'); li.textContent = c; ul.appendChild(li); });
}
function updateVoteStatus(vote) { document.getElementById('voteStatus').textContent = vote.status + ' – YES: ' + vote.yes + ' / NO: ' + vote.no; }
loadData();
