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

function toggleSpinnerAndButtonRow(objectType, actionBtnId, showCheckbox = true) {
  // objectType is container, image, or volume
  const checkboxes = $(`.tr-${objectType}-checkbox:checked`);
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

function performActionContainer(action, actionBtnId) {
  const checkedIds = $('.tr-container-checkbox:checked').map(function () {
    return this.value;
  }).get();
  // hide checkboxes
  $('.tr-container-checkbox:checked').css('display', 'none');
  // disable clicked action button
  $('#' + actionBtnId).prop('disabled', true);

  toggleSpinnerAndButtonRow('container', actionBtnId, false);

  $.ajax({
    url: `http://localhost:5002/api/containers/${action}`,
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ 'ids': checkedIds }),
    success: function (result) {
      toggleSpinnerAndButtonRow('container', actionBtnId);
    },
    error: function (result) {
      toggleSpinnerAndButtonRow('container', actionBtnId);
    }
  });
}

function performActionImage(action, actionBtnId) {
  // const image = $('#image-name').val();
  // const tag = $('#tag').val() === '' ? 'latest' : $('#tag').val();
  const checkedIds = $('.tr-image-checkbox:checked').map(function () {
    return this.value;
  }).get();
  // hide checkboxes
  $('.tr-image-checkbox:checked').css('display', 'none');
  // disable clicked action button
  $('#' + actionBtnId).prop('disabled', true);

  toggleSpinnerAndButtonRow('image', actionBtnId, false);

  $.ajax({
    url: `http://localhost:5002/api/images/${action}`,
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ 'ids': checkedIds }),
    success: function (result) {
      toggleSpinnerAndButtonRow('image', actionBtnId);
    },
    error: function (result) {
      toggleSpinnerAndButtonRow('image', actionBtnId);
    }
  });
}
