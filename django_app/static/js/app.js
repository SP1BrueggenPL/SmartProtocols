'use strict';

/* ── Document form: type switcher + dynamic rows ────────── */
function initDocumentForm(currentType) {
  const radios = document.querySelectorAll('input[name="doc_type"]');

  function applyType(type) {
    const isPhone   = type === 'telefon';
    const isOffice  = type === 'office';

    document.querySelectorAll('.section-equipment').forEach(el => {
      el.style.display = isPhone ? 'none' : '';
    });
    document.querySelectorAll('.section-phone').forEach(el => {
      el.style.display = isPhone ? '' : 'none';
    });
    document.querySelectorAll('.field-network-name').forEach(el => {
      el.style.display = isOffice ? '' : 'none';
    });

    // Toggle optgroups inside selects
    document.querySelectorAll('.opts-office').forEach(og => {
      og.style.display = type === 'office' ? '' : 'none';
    });
    document.querySelectorAll('.opts-produkcja').forEach(og => {
      og.style.display = type === 'produkcja' ? '' : 'none';
    });

    // Phone fields are not required when not shown
    document.querySelectorAll('.section-equipment input, .section-equipment select').forEach(el => {
      if (isPhone) el.removeAttribute('required');
    });
    document.querySelectorAll('.section-phone input').forEach(el => {
      el.removeAttribute('required');
    });
  }

  // Init on load
  applyType(currentType);

  radios.forEach(r => r.addEventListener('change', () => applyType(r.value)));

  /* ── Dynamic rows ───────────────────────────────────── */
  const addBtn = document.getElementById('addRowBtn');
  const tbody  = document.getElementById('equipmentRows');

  if (addBtn && tbody) {
    addBtn.addEventListener('click', () => {
      const firstRow = tbody.querySelector('.equipment-row');
      const newRow   = firstRow.cloneNode(true);

      // Clear values in the clone
      newRow.querySelectorAll('input').forEach(inp => {
        inp.value = inp.type === 'number' ? '1' : '';
      });
      newRow.querySelectorAll('select').forEach(sel => sel.selectedIndex = 0);

      tbody.appendChild(newRow);
      bindRemoveButtons();

      // Scroll into view
      newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      const firstInput = newRow.querySelector('select, input');
      if (firstInput) firstInput.focus();
    });
  }

  function bindRemoveButtons() {
    document.querySelectorAll('.remove-row').forEach(btn => {
      btn.onclick = function () {
        const rows = tbody.querySelectorAll('.equipment-row');
        if (rows.length > 1) {
          btn.closest('tr').remove();
        } else {
          // Clear last row instead of removing
          btn.closest('tr').querySelectorAll('input').forEach(inp => {
            inp.value = inp.type === 'number' ? '1' : '';
          });
          btn.closest('tr').querySelectorAll('select').forEach(sel => sel.selectedIndex = 0);
        }
      };
    });
  }

  bindRemoveButtons();

  /* ── Auto-set today's date if empty ─────────────────── */
  const dateInput = document.getElementById('doc_date');
  if (dateInput && !dateInput.value) {
    dateInput.value = new Date().toISOString().slice(0, 10);
  }
}
