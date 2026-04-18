$(document).ready(function(){

  function getCsrfToken() {
    // Try cookie first (works on HTTPS), fall back to DOM (works on HTTP dev)
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    if (match) return match[1];
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function getVersesUrl() {
    var container = document.querySelector('[data-verses-url]');
    return container ? container.getAttribute('data-verses-url') : '';
  }

  // Auto-load bible verse texts on detail pages
  var versesUrl = getVersesUrl();
  if (versesUrl) {
    console.debug('Loading bible verses from:', versesUrl);
    $.ajax({
      type: 'POST',
      url: versesUrl,
      data: { 'csrfmiddlewaretoken': getCsrfToken() },
      success: function(data) {
        if (data.verses) {
          $.each(data.verses, function(pk, text) {
            $('[data-verse-ref="' + pk + '"]').text(text);
          });
        }
      },
      error: function(xhr) {
        console.error('Failed to load bible verses:', xhr.status, xhr.responseText);
      }
    });
  }

  if($.cookie('jc_bible_trans_settings')){
    $('#changeLanguageModal').modal('show');
    $.removeCookie('jc_bible_trans_settings');
  }  
  if($.cookie('jc_kids_mode')){
    $('.chk-kids-mode').prop('checked', true);
    $('[targetaudience="kids"]').show();
    $('[targetaudience="adults"]').hide();
  }
  else {
    $('[targetaudience="kids"]').hide();
    $('[targetaudience="adults"]').show();
  }

  $(document).on('change', '.chk-kids-mode', function(event){
    // var checked = document.getElementById('chk-kids-mode-1').checked;
    var checked = $(this).prop('checked');
    if (checked){
      $.cookie('jc_kids_mode', true, { expires: 365 });
      $('[targetaudience="kids"]').slideDown();
      $('[targetaudience="adults"]').slideUp();
      $('.chk-kids-mode').prop('checked', true);
    }
    else {
      $.removeCookie('jc_kids_mode');
      $('[targetaudience="kids"]').slideUp();
      $('[targetaudience="adults"]').slideDown();
      $('.chk-kids-mode').prop('checked', false);
    }
  });

  const introVid = $("#WaJ-intro-video");
  if(introVid.length){
    const lang = $.cookie('django_language');
    if(lang === 'nl'){
      introVid.attr('src', 'https://www.youtube.com/embed/eTc08O8qEm0');
    } else {
      introVid.attr('src', '');
    }
  }



  // ----- Detailed commandments page: Smooth scrolling BEGIN ------ \\  
    // Add smooth scrolling to all links
    $("a").on('click', function(event) {

      // Make sure this.hash has a value before overriding default behavior
      if (this.hash !== "") {
        // Prevent default anchor click behavior
        event.preventDefault();

        // Store hash
        var hash = this.hash;

        // Using jQuery's animate() method to add smooth page scroll
        // The optional number (800) specifies the number of milliseconds it takes to scroll to the specified area
        $('html, body').animate({
          scrollTop: $(hash).offset().top
        }, 800, function(){

          // Add hash (#) to URL when done scrolling (default click behavior)
          window.location.hash = hash;
        });
      } // End if
    });
    // ----- Detailed commandments page: Smooth scrolling END ------ \\ 

    // ----- Study Listing arrows in table BEGIN ------ \\ 
    $('#dtBasicExample').DataTable();
      $('.dataTables_length').addClass('bs-select');
    // ----- Study Listing arrows in table END ------ \\ 

    // ----- Showing and hiding tooltip with different speed BEGIN ------ \\ 
    // $(".select").tooltip({
    //     delay: {show: 0, hide: 0}
    // });

    $(function () {
      $('[data-toggle="kids-tooltip"]').tooltip({ trigger: "hover" })
    })
    // ----- Showing and hiding tooltip with different speed END ------ \\ 

    $(document).on('change', '.drpSelectLanguage', function(event){
      event.preventDefault();
      $(this).trigger('jc:site-language-changed', [$(this).val()]);
    });
    $(document).on('change', '.drpBibleTranslation', function(event){
      event.preventDefault();
      $(this).trigger('jc:bible-translation-changed', [$(this).val()]);
    });

    $(document).on('click', '.btnSaveLanguages', function(event){
      event.preventDefault();
      $(this).trigger('jc:save-language-bible-settings');
    });

  });