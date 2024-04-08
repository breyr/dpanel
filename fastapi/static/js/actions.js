function getUrl() {
  let url;
  if (window.location.hostname === 'localhost') {
    url = `http://${window.location.hostname}:${window.location.port}`
  } else {
    url = `https://${window.location.hostname}`
  }
  return url;
}

function getInfo(containerId) {
  $.ajax({
    url: `${getUrl()}/api/containers/info/${containerId}`,
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
    if (port.PublicPort && port.IP === "0.0.0.0") {
      if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        var link = "http://" + window.location.hostname + ":" + port.PublicPort;
        result += `<a href=${link} target="_blank">${port.PublicPort}:${port.PrivatePort} <i class="bi bi-box-arrow-up-right"></i>`;
      } else {
        result += port.PublicPort + ':' + port.PrivatePort + "<br>";
      }
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
    url: `${getUrl()}/api/containers/${action}`,
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

  let checkedIds, image, tag;
  switch (action) {
    case 'delete':
      // get checked rows for images
      checkedIds = $('.tr-image-checkbox:checked').map(function () {
        return this.value;
      }).get();
      // hide checkboxes for image rows
      $('.tr-image-checkbox:checked').css('display', 'none');
      // disable clicked action button
      $('#' + actionBtnId).prop('disabled', true);
      // shows spinners for image rows
      toggleSpinnerAndButtonRow('image', actionBtnId, false);
      $.ajax({
        url: `${getUrl()}/api/images/${action}`,
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
      break;
    case 'pull':
      // get image input
      image = $('#image-name').val();
      // show error if image is ''
      if (image === '') {
        $('#pull-validation').append($("<small class='text-danger'></small").text("Please specify an image"));
      } else {
        // perform ajax call
        // get tag input
        tag = $('#tag').val() === '' ? 'latest' : $('#tag').val();
        // create random id
        // toggle icon and show spinner inside pull button
        const uniqueId = 'pull' + Date.now();
        $alert = `<p class='text-warning mt-2' id='${uniqueId}'><i class="bi bi-info-circle"></i> Pulling ${image}:${tag}</p>`;
        $('#pull-validation').append($alert);
        $.ajax({
          url: `${getUrl()}/api/images/${action}`,
          type: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({ 'image': image, 'tag': tag }),
          success: function (result) {
            // clear inputs after success only
            $('#image-name').val('');
            $('#tag').val('');
            $(`#${uniqueId}`).removeClass('text-warning').addClass('text-success');
            $(`#${uniqueId}`).html(`<i class="fa-regular fa-circle-check"></i> Successfully pulled ${image}:${tag}`);
            setTimeout(function () {
              $(`#${uniqueId}`).remove();
            }, 10000);  // 5000 milliseconds = 5 seconds
          },
          error: function (result) {
            $(`#${uniqueId}`).removeClass('text-warning').addClass('text-danger');
            $(`#${uniqueId}`).html(`<i class="fa-regular fa-circle-xmark"></i> Failed to pull ${image}:${tag} (double check the image name)`);
            setTimeout(function () {
              $(`#${uniqueId}`).remove();
            }, 10000);  // 5000 milliseconds = 5 seconds
          }
        });
      }
      break;
  }
}

function performActionCompose(action, projectName, event) {
  // function to handle compose up, compose down, delete (file)
  // show the spinner and diabled the button
  const clickedButton = event.target;
  $(clickedButton).find(".spinner-border").toggleClass('d-none');
  $(clickedButton).addClass('disabled');
  $.ajax({
    url: `${getUrl()}/api/compose/${action}`,
    method: "post",
    data: JSON.stringify({
      projectName
    }),
    success: function (res) {
      $(clickedButton).find(".spinner-border").toggleClass('d-none');
      $(clickedButton).removeClass('disabled');
    }
  });
}
