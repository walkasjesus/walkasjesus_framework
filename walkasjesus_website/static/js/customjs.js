$(document).ready(function(){

  var verseCache = {};
  var verseFetchInFlight = {};

  function collectRefIds(selector) {
    var ids = [];
    $(selector).each(function() {
      var pk = String($(this).attr('data-verse-ref') || '').trim();
      if (pk) {
        ids.push(pk);
      }
    });
    return Array.from(new Set(ids));
  }

  function fetchVerses(versesUrl, refIds, onDone) {
    if (!versesUrl || !refIds || refIds.length === 0) {
      if (onDone) onDone({});
      return;
    }

    $.ajax({
      type: 'POST',
      url: versesUrl,
      data: {
        csrfmiddlewaretoken: getCsrfToken(),
        verse_refs: refIds
      },
      success: function(data) {
        var verses = (data && data.verses) ? data.verses : {};
        $.each(verses, function(pk, text) {
          verseCache[String(pk)] = text;
        });
        if (onDone) onDone(verses);
      },
      error: function(xhr) {
        console.error('Failed to load bible verses:', xhr.status, xhr.responseText);
        if (onDone) onDone({});
      }
    });
  }

  function revealManualVerse($link, pk) {
    var text = verseCache[pk];
    if (typeof text === 'undefined') {
      return false;
    }

    $('.bible-verse-text[data-verse-ref="' + pk + '"][data-verse-manual="1"]').text(text);
    $link.hide();
    return true;
  }

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
    var autoRefIds = collectRefIds('.bible-verse-text[data-verse-ref]:not([data-verse-manual="1"])');
    if (autoRefIds.length > 0) {
      console.debug('Loading bible verses from:', versesUrl, 'refs:', autoRefIds.length);
      fetchVerses(versesUrl, autoRefIds, function(verses) {
        $.each(verses, function(pk, text) {
          $('.bible-verse-text[data-verse-ref="' + pk + '"]:not([data-verse-manual="1"])').text(text);
        });
      });
    }
  }

  $(document).on('click', '.bible-verse-load-link', function(event) {
    event.preventDefault();
    var $link = $(this);
    var pk = String($link.attr('data-verse-ref'));

    if (!revealManualVerse($link, pk)) {
      if (verseFetchInFlight[pk]) {
        return;
      }

      verseFetchInFlight[pk] = true;
      $('.bible-verse-text[data-verse-ref="' + pk + '"][data-verse-manual="1"]').html('<i class="fa fa-spinner fa-spin"></i>');
      fetchVerses(versesUrl, [pk], function() {
        revealManualVerse($link, pk);
        verseFetchInFlight[pk] = false;
      });
    }
  });

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