
// Modal handling and simple helpers
function openModal(id){var el=document.getElementById(id); if(el) el.style.display='flex'}
function closeModal(id){var el=document.getElementById(id); if(el) el.style.display='none'}
window.addEventListener('click', function(e){ document.querySelectorAll('.modal').forEach(function(m){ if(e.target===m) m.style.display='none' }) });
function openInvestmentModal(firmId, firmName){ var hid=document.getElementById('invest-firm-id'); if(hid) hid.value=firmId; openModal('investModal') }
 function togglePopup() {
      const popup = document.getElementById("popup");
      popup.style.display = (popup.style.display === "block") ? "none" : "block";
    }

function copyWallet() {
  const wallet = document.getElementById("wallet-address").innerText;
  navigator.clipboard.writeText(wallet).then(() => {
    alert("Wallet address copied to clipboard!");
  });
}

 function calculateProjectedValue(amount, createdAt, status) {
    if (status !== 'completed') return amount.toFixed(2);

    const createdDate = new Date(createdAt);
    const now = new Date();
    const diffTime = now - createdDate;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    const periods = Math.floor(diffDays / 30);
    const projected = amount * (1 + 0.05 * periods);

    return projected.toFixed(2);
  }

  document.querySelectorAll('tbody tr').forEach(row => {
    const amountEl = row.querySelector('.amount');
    const createdAtEl = row.querySelector('.created_at');
    const projectedValueEl = row.querySelector('.projected_value');

    if (amountEl && createdAtEl && projectedValueEl) {
      const amount = parseFloat(amountEl.textContent);
      const createdAt = createdAtEl.dataset.date;
      const status = projectedValueEl.dataset.status;

      projectedValueEl.textContent = calculateProjectedValue(amount, createdAt, status);
    }
  });

  function togglePassword(id) {
  const field = document.getElementById(id);
  if (field.type === "password") {
    field.type = "text";
  } else {
    field.type = "password";
  }
}