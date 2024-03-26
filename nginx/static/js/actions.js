function getInfo(containerId) {
  $.ajax({
    url: `http://localhost:5002/api/containers/info/${containerId}`,
    type: 'GET',
    success: function (data) {
      // Create a new Blob from the JSON string
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      // Create an object URL from the Blob
      const url = URL.createObjectURL(blob);
      // Open the URL in a new tab
      window.open(url, '_blank');
    }
  });
}

function getStatusClass(status) {
  switch (status) {
    case "running": return "success";
    case "paused": return "warning";
    case "exited": return "danger";
    default: return "secondary";
  }
}

function getPortBindings(portBindings) {
  var result = "";
  $.each(portBindings, function (i, port) {
    if (port.PublicPort) {
      result += '<a href="http://localhost:' + port.PublicPort + '" target="_blank">' + port.PrivatePort + ':' + port.PublicPort + ' <i class="bi bi-box-arrow-up-right"></i></a> ';
    }
  });
  return result;
}

function toggleSpinnerAndButton(actionBtnId, showCheckbox = true) {
  const checkboxes = $('.tr-checkbox:checked');
  checkboxes.each(function () {
    const row = $(this).closest('tr');
    row.find('.spinner-border').toggleClass('d-none');
    if (showCheckbox) {
      $(this).show();
      $(this).prop('checked', false);
    }
  });
  $('#' + actionBtnId).prop('disabled', false);
}

function performAction(action, actionBtnId) {
  const checkedIds = $('.tr-checkbox:checked').map(function () {
    return this.value;
  }).get();
  // hide checkboxes
  $('.tr-checkbox:checked').css('display', 'none');
  // disable clicked action button
  $('#' + actionBtnId).prop('disabled', true);

  toggleSpinnerAndButton(actionBtnId, false);

  $.ajax({
    url: `http://localhost:5002/api/containers/${action}`,
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ 'ids': checkedIds }),
    success: function (result) {
      toggleSpinnerAndButton(actionBtnId);
    },
    error: function (result) {
      toggleSpinnerAndButton(actionBtnId);
    }
  });
}
