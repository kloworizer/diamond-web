(function(){
  function findWrapper(el){
    if(!el) return null;
    var p = el.parentElement;
    for(var i=0;i<6 && p;i++){
      if(p.classList && (p.classList.contains('mb-3') || p.classList.contains('form-group'))) return p;
      if(p.id && p.id.indexOf('div_id_')===0) return p;
      p = p.parentElement;
    }
    return null;
  }

  function hideField(el){ if(!el) return; var w=findWrapper(el); if(w) w.style.display='none'; else el.style.display='none'; }
  function showField(el){ if(!el) return; var w=findWrapper(el); if(w) w.style.display='block'; else el.style.display='block'; }

  var ilap = document.getElementById('id_id_ilap') || document.querySelector('[name="id_ilap"]');
  var jenisSelect = document.getElementById('id_id_jenis_data') || document.querySelector('[name="id_jenis_data"]');
  var namaInput = document.getElementById('id_nama_jenis_data') || document.querySelector('[name="nama_jenis_data"]');

  if(!ilap) return;

  // hide jenis and nama initially (wizard step 1 only shows ilap)
  hideField(jenisSelect);
  hideField(namaInput);

  // create a new input for generated id (step 2 option)
  var newIdInput = document.createElement('input');
  newIdInput.type = 'text';
  newIdInput.name = 'id_jenis_data_new';
  newIdInput.id = 'id_id_jenis_data_new';
  newIdInput.className = 'form-control';
  newIdInput.readOnly = true;

  var newWrapper = document.createElement('div');
  newWrapper.className = 'mb-3';
  var newLabel = document.createElement('label');
  newLabel.htmlFor = newIdInput.id;
  newLabel.innerText = 'ID Jenis Data (baru)';
  newWrapper.appendChild(newLabel);
  newWrapper.appendChild(newIdInput);
  newWrapper.style.display = 'none';

  // checkbox to choose using new id
  var useNewWrapper = document.createElement('div');
  useNewWrapper.className = 'form-check mb-3';
  var useNewCheckbox = document.createElement('input');
  useNewCheckbox.type = 'checkbox';
  useNewCheckbox.id = 'id_use_new_jenis_data';
  useNewCheckbox.className = 'form-check-input';
  var useNewLabel = document.createElement('label');
  useNewLabel.className = 'form-check-label';
  useNewLabel.htmlFor = useNewCheckbox.id;
  useNewLabel.innerText = 'Gunakan ID Jenis Data Baru';
  useNewWrapper.appendChild(useNewCheckbox);
  useNewWrapper.appendChild(useNewLabel);
  (function(){
    function findWrapper(el){
      if(!el) return null;
      var p = el.parentElement;
      for(var i=0;i<6 && p;i++){
        if(p.classList && p.classList.contains('jenis-wizard-block')) { p = p.parentElement; continue; }
        if(p.classList && (p.classList.contains('mb-3') || p.classList.contains('form-group'))) return p;
        if(p.id && p.id.indexOf('div_id_')===0) return p;
        p = p.parentElement;
      }
      return null;
    }
    function hideField(el){ if(!el) return; var w=findWrapper(el); if(w) w.style.display='none'; else el.style.display='none'; }
    function showField(el){ if(!el) return; var w=findWrapper(el); if(w) w.style.display='block'; else el.style.display='block'; }

    // Setup wizard for a single form element. This allows re-initializing when modal HTML is loaded dynamically.
    function setupForm(form){
      if(!form || form.dataset.jenisWizardInitialized) return;
      var ilap = form.querySelector('#id_id_ilap') || form.querySelector('[name="id_ilap"]');
      var jenisSelect = form.querySelector('#id_id_jenis_data') || form.querySelector('[name="id_jenis_data"]');
      var namaInput = form.querySelector('#id_nama_jenis_data') || form.querySelector('[name="nama_jenis_data"]');
      if(!ilap) return;

      // Hide fields initially
      if(jenisSelect) hideField(jenisSelect);
      if(namaInput) hideField(namaInput);

      // create elements scoped inside this form
      var newIdInput = document.createElement('input');
      newIdInput.type = 'text'; newIdInput.name = 'id_jenis_data_new'; newIdInput.className = 'form-control'; newIdInput.readOnly = true;
      var newWrapper = document.createElement('div'); newWrapper.className = 'mb-3';
      var newLabel = document.createElement('label'); newLabel.innerText = 'ID Jenis Data (baru)'; newWrapper.appendChild(newLabel); newWrapper.appendChild(newIdInput); newWrapper.style.display = 'none';

      var useNewWrapper = document.createElement('div'); useNewWrapper.className = 'form-check mb-3';
      var useNewCheckbox = document.createElement('input'); useNewCheckbox.type = 'checkbox'; useNewCheckbox.className = 'form-check-input';
      var useNewLabel = document.createElement('label'); useNewLabel.className = 'form-check-label'; useNewLabel.innerText = 'Gunakan ID Jenis Data Baru';
      useNewWrapper.appendChild(useNewCheckbox); useNewWrapper.appendChild(useNewLabel); useNewWrapper.style.display = 'none';

      var insAfter = findWrapper(ilap) || ilap;
      // create a block container to hold the wizard fields in order for readability
      var blockContainer = document.createElement('div');
      blockContainer.className = 'jenis-wizard-block mb-3';
      if(insAfter && insAfter.parentNode){
        insAfter.parentNode.insertBefore(blockContainer, insAfter.nextSibling);
        // append elements in the requested order for readability
        blockContainer.appendChild(useNewWrapper);
        blockContainer.appendChild(newWrapper);
        // move existing nama jenis wrapper (if present) into the block after the new-id
        try{
          var namaWrapper = namaInput ? findWrapper(namaInput) : null;
          if(namaWrapper) blockContainer.appendChild(namaWrapper);
        }catch(e){}
        // move original jenis input wrapper (so the dropdown/backup sits in the block)
        try{
          var originalJenis = form.querySelector('#id_id_jenis_data') || form.querySelector('[name="id_jenis_data"]');
          var originalJenisWrapper = originalJenis ? findWrapper(originalJenis) : null;
          if(originalJenisWrapper) blockContainer.appendChild(originalJenisWrapper);
        }catch(e){}
      }

      // hide the whole wizard block initially; only show after ILAP selection
      try{ blockContainer.style.display = 'none'; }catch(e){}

      var hiddenChosenId = document.createElement('input'); hiddenChosenId.type='hidden'; hiddenChosenId.name='id_jenis_data'; form.appendChild(hiddenChosenId);
      // track next id result for current ILAP to avoid showing sub controls too early
      var pendingNextId = null;
      // Sub-jenis elements
      var subField = form.querySelector('#id_id_sub_jenis_data') || form.querySelector('[name="id_sub_jenis_data"]');
      var namaSub = form.querySelector('#id_nama_sub_jenis_data') || form.querySelector('[name="nama_sub_jenis_data"]');
      var hiddenSubChosen = document.createElement('input'); hiddenSubChosen.type='hidden'; hiddenSubChosen.name='id_sub_jenis_data'; form.appendChild(hiddenSubChosen);
      var newSubInput = document.createElement('input'); newSubInput.type='text'; newSubInput.name='id_sub_jenis_data_new'; newSubInput.className='form-control'; newSubInput.readOnly=true;
      var newSubWrapper = document.createElement('div'); newSubWrapper.className='mb-3'; var newSubLabel = document.createElement('label'); newSubLabel.innerText='ID Sub Jenis Data (baru)'; newSubWrapper.appendChild(newSubLabel); newSubWrapper.appendChild(newSubInput); newSubWrapper.style.display='none';
      var useNewSubWrapper = document.createElement('div'); useNewSubWrapper.className='form-check mb-3'; var useNewSubCheckbox = document.createElement('input'); useNewSubCheckbox.type='checkbox'; useNewSubCheckbox.className='form-check-input'; var useNewSubLabel = document.createElement('label'); useNewSubLabel.className='form-check-label'; useNewSubLabel.innerText='Gunakan ID Sub Jenis Data Baru'; useNewSubWrapper.appendChild(useNewSubCheckbox); useNewSubWrapper.appendChild(useNewSubLabel); useNewSubWrapper.style.display='none';
      // insert sub wrappers into the same block container
      if(blockContainer){
        blockContainer.appendChild(useNewSubWrapper);
        blockContainer.appendChild(newSubWrapper);
        // move existing nama sub wrapper into block next to new sub input
        try{
          var namaSubWrapper = namaSub ? findWrapper(namaSub) : null;
          if(namaSubWrapper) blockContainer.appendChild(namaSubWrapper);
        }catch(e){}
        // move original sub input wrapper into block so dropdown appears in correct place
        try{
          var originalSubEl = form.querySelector('#id_id_sub_jenis_data') || form.querySelector('[name="id_sub_jenis_data"]');
          var originalSubWrapper = originalSubEl ? findWrapper(originalSubEl) : null;
          if(originalSubWrapper) blockContainer.appendChild(originalSubWrapper);
        }catch(e){}
      } else if(insAfter && insAfter.parentNode){
        insAfter.parentNode.insertBefore(useNewSubWrapper, newWrapper.nextSibling);
        insAfter.parentNode.insertBefore(newSubWrapper, useNewSubWrapper.nextSibling);
      }
      // try to locate the jenis tabel field and move it into the block container so it appears after sub-jenis
      try{
        var jenisTabel = form.querySelector('#id_id_jenis_tabel') || form.querySelector('[name="id_jenis_tabel"]');
        var jenisTabelWrapper = jenisTabel ? findWrapper(jenisTabel) : null;
        if(jenisTabelWrapper && blockContainer){ blockContainer.appendChild(jenisTabelWrapper); }
      }catch(e){}

      // preserve options lazily
      function ensureAllOptions(){
        if(!jenisSelect) return [];
        if(!jenisSelect._allOptions){
          jenisSelect._allOptions = jenisSelect.options ? Array.from(jenisSelect.options) : [];
        }
        return jenisSelect._allOptions;
      }

      function populateSelectForIlap(prefix){
        // Ensure we have a select element to populate. If the form originally had a text input,
        // create a select and hide the original input so user can choose existing IDs.
        if(!jenisSelect || jenisSelect.tagName !== 'SELECT'){
          var original = form.querySelector('#id_id_jenis_data') || form.querySelector('[name="id_jenis_data"]');
          var sel = document.createElement('select');
          sel.name = 'id_jenis_data';
          sel.id = original && original.id ? original.id : 'id_id_jenis_data';
          sel.className = original && original.className ? original.className : 'form-select';
          // hide original input if present
          if(original){
            original.style.display = 'none';
            try{ original.name = original.name ? 'backup_'+original.name : ''; }catch(e){}
            try{ original.required = false; original.removeAttribute && original.removeAttribute('required'); original.disabled = true; }catch(e){}
            // Prefer inserting the select into the original field wrapper so it appears under the same label
            try{
              var originalWrapper = findWrapper(original);
              if(originalWrapper){
                originalWrapper.appendChild(sel);
              } else if(blockContainer){
                blockContainer.appendChild(sel);
              } else if(original.parentNode){
                original.parentNode.insertBefore(sel, original.nextSibling);
              }
            }catch(e){ if(blockContainer) blockContainer.appendChild(sel); else if(original.parentNode) original.parentNode.insertBefore(sel, original.nextSibling); }
            } else {
            // fallback: append to block or form
            if(blockContainer) blockContainer.appendChild(sel); else form.appendChild(sel);
          }
          jenisSelect = sel;
          try{ if(typeof wireJenisChange === 'function') wireJenisChange(jenisSelect); }catch(e){}
        }

        // clear any existing options
        jenisSelect.innerHTML = '';
        // add a null/default option like the ILAP dropdown
        try{ var nullOpt = document.createElement('option'); nullOpt.value = ''; nullOpt.text = '-- Pilih ID Jenis Data --'; jenisSelect.appendChild(nullOpt); }catch(e){}

        // fetch existing items from server endpoint
        var url = '/jenis-data/existing/?ilap_id=' + encodeURIComponent(prefix);
        fetch(url, {credentials: 'same-origin'})
          .then(function(resp){ return resp.json(); })
          .then(function(data){
              var items = (data && data.items) ? data.items : [];
              if(items.length === 0){
                var opt = document.createElement('option'); opt.value = ''; opt.text = '-- Tidak ada --'; jenisSelect.appendChild(opt);
                // no existing IDs -> force use new and disable the checkbox so user can't uncheck
                try{ useNewCheckbox.checked = true; useNewCheckbox.disabled = true; setUsingNew(true); }catch(e){}
                // ensure the generated new-id input is visible and the jenis select is hidden
                try{ if(jenisSelect){ hideField(jenisSelect); jenisSelect.disabled = true; jenisSelect.style.display='none'; } }catch(e){}
                try{ newWrapper.style.display = 'block'; showField(newWrapper); }catch(e){}
                // also force sub-new and show sub-new controls
                try{ useNewSubCheckbox.checked = true; useNewSubCheckbox.disabled = true; useNewSubWrapper.style.display = 'block'; showField(useNewSubWrapper); newSubWrapper.style.display = 'block'; showField(newSubWrapper); setUsingNewSub(true); }catch(e){}
                // if next-id already fetched, compute sub-id now
                try{ if(pendingNextId){ hiddenChosenId.value = pendingNextId; computeSubForNewId(pendingNextId); } }catch(e){}
              } else {
                items.forEach(function(it){ var opt = document.createElement('option'); opt.value = it.value; opt.text = it.text; jenisSelect.appendChild(opt); });
                // existing IDs found -> ensure not using new by default and enable the checkbox
                try{
                  useNewCheckbox.disabled = false; useNewCheckbox.checked = false;
                  // ensure the jenis select/wrapper is visible and placed before sub controls
                  try{
                    var jenisWrapper = findWrapper(jenisSelect);
                    if(jenisWrapper){
                      jenisWrapper.style.display = 'block';
                      if(blockContainer && useNewSubWrapper && blockContainer.contains(useNewSubWrapper)){
                        blockContainer.insertBefore(jenisWrapper, useNewSubWrapper);
                      }
                    }
                    if(jenisSelect) { jenisSelect.disabled = false; jenisSelect.style.display=''; }
                  }catch(e){}
                  setUsingNew(false);
                }catch(e){}
                // Explicitly hide/clear all sub-jenis controls until a jenis is chosen
                try{ useNewSubCheckbox.checked = false; useNewSubCheckbox.disabled = false; useNewSubWrapper.style.display = 'none'; }catch(e){}
                try{ if(newSubWrapper) newSubWrapper.style.display = 'none'; }catch(e){}
                try{ if(subField){ var origSub = form.querySelector('#id_id_sub_jenis_data') || form.querySelector('[name="id_sub_jenis_data"]'); var origSubWrap = origSub ? findWrapper(origSub) : null; if(origSubWrap) origSubWrap.style.display='none'; hideField(subField); } }catch(e){}
                try{ hiddenSubChosen.value = ''; if(namaSub){ namaSub.value=''; hideField(namaSub); namaSub.required=false; } }catch(e){}
                // set hidden value and sync name for the first option
                try{ if(jenisSelect.options && jenisSelect.options.length){
                  var sel = jenisSelect.options[jenisSelect.selectedIndex >= 0 ? jenisSelect.selectedIndex : 0];
                  if(sel){ hiddenChosenId.value = sel.value; var parts = (sel.text || '').split(' - '); if(namaInput) { namaInput.value = parts.length>1?parts.slice(1).join(' - ').trim():parts[0]; hideField(namaInput); namaInput.required = false; } }
                }}catch(e){}
              }
            }).catch(function(){
            // on error fallback to any cached options
            var all = ensureAllOptions();
            if(all.length){
              all.forEach(function(opt){ jenisSelect.appendChild(opt.cloneNode(true)); });
            }
          });
      }

      function setUsingNew(flag){
        if(flag){
          newWrapper.style.display='block';
          // hide the dropdown wrapper explicitly
          try{ var jenisWrapper = findWrapper(jenisSelect); if(jenisWrapper) jenisWrapper.style.display='none'; }catch(e){}
          if(jenisSelect){ jenisSelect.disabled=true; }
          // show and clear nama field
          try{ var namaWrapper = findWrapper(namaInput); if(namaWrapper) namaWrapper.style.display='block'; }catch(e){}
          if(namaInput){ namaInput.value = ''; namaInput.required=true; }
          hiddenChosenId.value = newIdInput.value || '';
          // compute next sub id for this new jenis and set it (may fetch if not yet available)
          var idForSub = newIdInput.value || hiddenChosenId.value;
          if(idForSub){
            computeSubForNewId(idForSub);
          } else {
            // if main new id isn't available yet, wait — computeSubForNewId will be called when newIdInput is set
          }
          // when main new is used, force sub to be new and disable toggling
          try{ useNewSubCheckbox.checked = true; useNewSubCheckbox.disabled = true; setUsingNewSub(true); }catch(e){}
        } else {
          newWrapper.style.display='none';
          // show the dropdown wrapper explicitly
          try{ var jenisWrapper = findWrapper(jenisSelect); if(jenisWrapper) jenisWrapper.style.display='block'; }catch(e){}
          if(jenisSelect){ jenisSelect.disabled=false; }
          // reset dropdown to default null value when switching back
          try{ if(jenisSelect){ jenisSelect.value=''; if(jenisSelect.selectedIndex !== undefined) jenisSelect.selectedIndex = 0; } }catch(e){}
          // hide nama field
          try{ var namaWrapper = findWrapper(namaInput); if(namaWrapper) namaWrapper.style.display='none'; }catch(e){}
          if(namaInput){ namaInput.required=false; namaInput.value=''; }
          hiddenChosenId.value='';
          // hide sub-jenis controls until a jenis is chosen
          try{ useNewSubCheckbox.checked = false; useNewSubCheckbox.disabled = false; if(useNewSubWrapper) useNewSubWrapper.style.display='none'; }catch(e){}
          try{ if(newSubWrapper) newSubWrapper.style.display='none'; }catch(e){}
          try{ if(subField){ hideField(subField); subField.style.display='none'; } }catch(e){}
          try{ if(namaSub){ namaSub.value=''; hideField(namaSub); namaSub.required=false; } }catch(e){}
        }
      }

      // helper to compute next sub id for a given new jenis id
      function computeSubForNewId(idForSub){
        if(!idForSub) return;
        var subUrl = '/jenis-data/sub/next/?id_jenis_data=' + encodeURIComponent(idForSub);
        fetch(subUrl, {credentials: 'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
          if(d && d.next_id){
            // Show the use-new sub checkbox checked and disabled
            try{ useNewSubCheckbox.checked = true; useNewSubCheckbox.disabled = true; useNewSubWrapper.style.display = 'block'; showField(useNewSubWrapper); }catch(e){}
            // Show the new sub id field with the calculated value
            newSubInput.value = d.next_id;
            hiddenSubChosen.value = d.next_id;
            newSubWrapper.style.display = 'block';
            showField(newSubWrapper);
            // Show the nama sub field
            try{ if(namaSub){ namaSub.value = ''; showField(namaSub); namaSub.required = true; } }catch(e){}
          }
        }).catch(function(){});
      }

      ilap.addEventListener('change', function(){
        var value = '';
        if(ilap.tagName === 'SELECT' && ilap.options && ilap.selectedIndex >= 0){
          var selText = (ilap.options[ilap.selectedIndex].text || '').trim();
          var m = selText.match(/[A-Za-z0-9]+/);
          value = m ? m[0] : selText;
        }
        if(!value) value = (ilap.value || '').trim();
        pendingNextId = null;
        // clear any previously generated ids to avoid using stale values
        try{ if(newIdInput) newIdInput.value = ''; }catch(e){}
        try{ if(newSubInput) newSubInput.value = ''; }catch(e){}
        // reset main use-new state immediately to avoid stale forced-new behavior
        try{ useNewCheckbox.checked = false; useNewCheckbox.disabled = false; }catch(e){}
        try{ if(newWrapper) newWrapper.style.display = 'none'; }catch(e){}

        // IMMEDIATELY clear previously selected names/hidden values and hide all sub controls
        try{ if(namaInput){ namaInput.value=''; hideField(namaInput); namaInput.required=false; } }catch(e){}
        try{ if(namaSub){ namaSub.value=''; hideField(namaSub); namaSub.required=false; } }catch(e){}
        try{ hiddenChosenId.value=''; hiddenSubChosen.value=''; }catch(e){}
        // Hide all sub-jenis controls immediately
        try{ useNewSubCheckbox.checked = false; useNewSubCheckbox.disabled = false; useNewSubWrapper.style.display = 'none'; }catch(e){}
        try{ if(newSubWrapper) newSubWrapper.style.display='none'; }catch(e){}
        try{ if(subField){ hideField(subField); subField.style.display='none'; } }catch(e){}
        try{ if(setUsingNewSub) setUsingNewSub(false); }catch(e){}

        if(!value){
          try{ if(blockContainer) blockContainer.style.display = 'none'; }catch(e){}
          try{ useNewWrapper.style.display='none'; newWrapper.style.display='none'; }catch(e){}
          return;
        }

        try{ if(blockContainer) blockContainer.style.display = 'block'; }catch(e){}
        try{ useNewWrapper.style.display='block'; }catch(e){}
        setUsingNew(useNewCheckbox.checked);

        // ensure jenis_tabel is visible
        try{ var jenisTabel = form.querySelector('#id_id_jenis_tabel') || form.querySelector('[name="id_jenis_tabel"]'); var jenisTabelWrap = jenisTabel?findWrapper(jenisTabel):null; if(jenisTabelWrap) jenisTabelWrap.style.display='block'; }catch(e){}

        populateSelectForIlap(value);

        var url = '/jenis-data/get-next-id/?ilap_id=' + encodeURIComponent(value);
        fetch(url, {credentials: 'same-origin'}).then(function(resp){ return resp.json(); }).then(function(data){
          if(data && data.next_id){
            newIdInput.value = data.next_id;
            pendingNextId = data.next_id;
            try{
              if(useNewCheckbox.checked && useNewCheckbox.disabled){
                hiddenChosenId.value = data.next_id;
                computeSubForNewId(data.next_id);
              }
            }catch(e){}
          }
        }).catch(function(){});
      });

      useNewCheckbox.addEventListener('change', function(){ setUsingNew(this.checked); if(this.checked && newIdInput) hiddenChosenId.value = newIdInput.value || ''; });

      // when jenisSelect changes, sync hidden and populate sub-jenis
      function wireJenisChange(sel){
        if(!sel || sel._jenisChangeWired) return;
        sel._jenisChangeWired = true;
        sel.addEventListener('change', function(){
          try{ hiddenChosenId.value = sel.value || (sel.options && sel.options[sel.selectedIndex] && sel.options[sel.selectedIndex].value) || ''; }catch(e){}
          try{ var selText = sel.options[sel.selectedIndex].text || ''; var parts = selText.split(' - '); if(namaInput){ namaInput.value = parts.length>1?parts.slice(1).join(' - ').trim():parts[0]; hideField(namaInput); namaInput.required = false; } }catch(e){}
          // populate sub list
          populateSubForJenis(hiddenChosenId.value || sel.value);
        });
      }
      if(jenisSelect) wireJenisChange(jenisSelect);

      // populate sub-jenis for a given jenis id
      function populateSubForJenis(idJenis){
        if(!idJenis) return;
        var subSelect = subField;
        var originalSub = form.querySelector('#id_id_sub_jenis_data') || form.querySelector('[name="id_sub_jenis_data"]');
        if(!subSelect || subSelect.tagName !== 'SELECT'){
          var sel = document.createElement('select'); sel.name = 'id_sub_jenis_data'; sel.id = originalSub && originalSub.id ? originalSub.id : 'id_id_sub_jenis_data'; sel.className = originalSub && originalSub.className ? originalSub.className : 'form-select';
          if(originalSub){ try{ originalSub.style.display='none'; originalSub.required=false; originalSub.removeAttribute && originalSub.removeAttribute('required'); originalSub.disabled=true; originalSub.name = originalSub.name ? 'backup_'+originalSub.name : ''; if(blockContainer) { try{ var jenisTabel = form.querySelector('#id_id_jenis_tabel') || form.querySelector('[name="id_jenis_tabel"]'); var jenisTabelWrap = jenisTabel ? findWrapper(jenisTabel) : null; if(jenisTabelWrap && blockContainer.contains(jenisTabelWrap)){ blockContainer.insertBefore(sel, jenisTabelWrap); } else { blockContainer.appendChild(sel); } }catch(e){ blockContainer.appendChild(sel); } } else if(originalSub.parentNode) originalSub.parentNode.insertBefore(sel, originalSub.nextSibling);}catch(e){} } else { if(blockContainer) { try{ var jenisTabel = form.querySelector('#id_id_jenis_tabel') || form.querySelector('[name="id_jenis_tabel"]'); var jenisTabelWrap = jenisTabel ? findWrapper(jenisTabel) : null; if(jenisTabelWrap && blockContainer.contains(jenisTabelWrap)){ blockContainer.insertBefore(sel, jenisTabelWrap); } else { blockContainer.appendChild(sel); } }catch(e){ blockContainer.appendChild(sel); } } else form.appendChild(sel); }
          subSelect = sel; subField = sel;
        }
        subSelect.innerHTML = '';
        // Always force new sub when a jenis is selected: hide dropdown, show new-sub checked
        try{
          var subWrap = findWrapper(subSelect);
          if(subWrap && subWrap !== blockContainer){
            subWrap.style.display = 'none';
          } else if(subSelect){
            subSelect.style.display = 'none';
          }
          subSelect.disabled = true;
        }catch(e){}
        try{ useNewSubCheckbox.checked = true; useNewSubCheckbox.disabled = true; useNewSubWrapper.style.display = 'block'; showField(useNewSubWrapper); }catch(e){}
        var nextUrl = '/jenis-data/sub/next/?id_jenis_data=' + encodeURIComponent(idJenis);
        fetch(nextUrl, {credentials:'same-origin'}).then(function(rr){ return rr.json(); }).then(function(dd){
          if(dd && dd.next_id){
            newSubInput.value = dd.next_id;
            hiddenSubChosen.value = dd.next_id;
            newSubWrapper.style.display = 'block';
            showField(newSubWrapper);
            try{ if(namaSub){ namaSub.value=''; showField(namaSub); namaSub.required=true; } }catch(e){}
            try{ setUsingNewSub(true); }catch(e){}
          }
        }).catch(function(){});
        // wire change
        (function(s){ if(s && s.addEventListener){ s.addEventListener('change', function(){ hiddenSubChosen.value = s.value; try{ var parts = (s.options[s.selectedIndex].text||'').split(' - '); if(namaSub){ namaSub.value = parts.length>1?parts.slice(1).join(' - ').trim():parts[0]; hideField(namaSub); namaSub.required=false; } }catch(e){} }); } })(subSelect);
      }

      function setUsingNewSub(flag){
        if(flag){
          newSubWrapper.style.display='block';
          if(subField){
            try{
              var subWrap = findWrapper(subField);
              if(subWrap && subWrap !== blockContainer){
                subWrap.style.display = 'none';
              } else {
                subField.style.display = 'none';
              }
            }catch(e){}
            subField.disabled = true;
          }
          if(namaSub){ namaSub.required=true; showField(namaSub); }
          hiddenSubChosen.value = newSubInput.value || '';
        } else {
          newSubWrapper.style.display='none';
          if(subField){
            try{
              var subWrapShow = findWrapper(subField);
              if(subWrapShow && subWrapShow !== blockContainer){
                subWrapShow.style.display = 'block';
              } else {
                subField.style.display = '';
              }
            }catch(e){}
            subField.disabled = false;
          }
          if(namaSub){ namaSub.required=false; }
          hiddenSubChosen.value='';
        }
      }

      useNewSubCheckbox.addEventListener('change', function(){ setUsingNewSub(this.checked); if(this.checked && newSubInput){ hiddenSubChosen.value = newSubInput.value || ''; } });

      form.addEventListener('submit', function(e){
        if(useNewCheckbox.checked){ if(!hiddenChosenId.value) hiddenChosenId.value = newIdInput.value || ''; if(namaInput && !namaInput.value){ namaInput.focus(); e.preventDefault(); return; } }
        if(useNewSubCheckbox.checked){ if(!hiddenSubChosen.value) hiddenSubChosen.value = newSubInput.value || ''; if(namaSub && !namaSub.value){ namaSub.focus(); e.preventDefault(); return; } }
      });

      // mark initialized
      form.dataset.jenisWizardInitialized = '1';
    }

    // initialize existing forms on page
    document.querySelectorAll('form.form-modal, form').forEach(function(f){ setupForm(f); });

    // observe DOM insertions to initialize forms loaded via AJAX/modal
    var mo = new MutationObserver(function(muts){
      muts.forEach(function(m){
        Array.from(m.addedNodes || []).forEach(function(node){
          if(node.nodeType !== 1) return;
          if(node.matches && node.matches('form.form-modal, form')) setupForm(node);
          // also search inside node for forms
          node.querySelectorAll && node.querySelectorAll('form.form-modal, form').forEach(function(f){ setupForm(f); });
        });
      });
    });
    mo.observe(document.body, { childList: true, subtree: true });
  })();
})();
