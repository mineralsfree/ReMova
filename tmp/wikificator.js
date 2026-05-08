// <nowiki>
mw.loader.using(
  "jquery.client",
  (function () {
    var clientProfile = $.client.profile();
    var hotkey =
      clientProfile.platform === "mac" ? "Ctrl+Shift+W" : "Ctrl+Alt+W";
    var strings = {
      name: "Вікіфікатар",
      tooltip:
        "Вікіфікатар — інструмент для аўтаматычнай апрацоўкі тэкста (" +
        hotkey +
        ")",
      summary: "вікіфікатар",
      fullText:
        "Вікіфікатар апрацуе ўвесь тэкст на гэтай старонцы. Працягнуць?",
      talkPage:
        "Вікіфікатар не апрацоўвае старонкі абмеркавання цалкам.\n\nВылучыце вашае паведамленне — апрацаванае будзе толькі яно.",
    };
    window.wfPlugins = window.wfPlugins || [];
    window.wfPluginsT = window.wfPluginsT || [];

    // Function takes an input or text as an argument. If it is absent, it uses $( '#wpTextbox1' )
    // as an input.
    window.Wikify = function (input) {
      "use strict";

      // FUNCTIONS

      function r(r1, r2) {
        txt = txt.replace(r1, r2);
      }

      function hide(re) {
        r(re, function (s) {
          return "\x01" + hidden.push(s) + "\x02";
        });
      }

      function hideTag(tag) {
        hide(
          new RegExp("<" + tag + "( [^>]+)?>[\\s\\S]+?<\\/" + tag + ">", "gi"),
        );
      }

      function hideTemplates() {
        hide(/\{\{([^{]\{?)+?\}\}/g);
        var pos = 0,
          stack = [],
          tpl,
          left,
          right;
        while (true) {
          left = txt.indexOf("{{", pos);
          right = txt.indexOf("}}", pos);
          if (left === -1 && right === -1 && !stack.length) {
            break;
          }
          if (left !== -1 && (left < right || right === -1)) {
            stack.push(left);
            pos = left + 2;
          } else {
            left = stack.pop();
            if (typeof left === "undefined") {
              if (right === -1) {
                pos += 2;
                continue;
              } else {
                left = 0;
              }
            }
            if (right === -1) {
              right = txt.length;
            }
            right += 2;
            tpl = txt.substring(left, right);
            txt =
              txt.substring(0, left) +
              "\x01" +
              hidden.push(tpl) +
              "\x02" +
              txt.substr(right);
            pos = right - tpl.length;
          }
        }
      }

      function processLink(link, left, right) {
        left = $.trim(left.replace(/[ _\u00A0]+/g, " "));
        if (left.match(/^(?:Катэгорыя|Файл) ?:/)) {
          return "[[" + left + "|" + right + "]]";
        }
        right = $.trim(right.replace(/ {2,}/g, " "));
        var inLink = right.substr(0, left.length);
        var afterLink = right.substr(left.length);
        var uniLeft = left.substr(0, 1).toUpperCase() + left.substr(1);
        var uniRight = (
          right.substr(0, 1).toUpperCase() + right.substr(1)
        ).replace(/[_\u00A0]/g, " ");
        if (
          uniRight.indexOf(uniLeft) === 0 &&
          afterLink.match(/^[a-zа-яё]*$/)
        ) {
          return "[[" + inLink + "]]" + afterLink;
        } else {
          return "[[" + left + "|" + right + "]]";
        }
      }

      function processText() {
        var u = "\u00A0"; // non-breaking space
        if (
          mw.config.get("wgNamespaceNumber") % 2 ||
          mw.config.get("wgNamespaceNumber") === 4
        ) {
          // is talk page
          var sigs = txt.match(
            /\d\d:\d\d, \d\d? \S{3,11} 20\d\d \((\+03|MSK|UTC)\)/g,
          );
          if (sigs && sigs.length > 1) {
            alert(strings.talkPage);
            return;
          }
        }

        hideTag("nowiki");
        hideTag("pre");
        hideTag("source");
        hideTag("syntaxhighlight");
        hideTag("templatedata");

        hideTag("code");
        hideTag("kbd");
        hideTag("tt");

        hideTag("graph");
        hideTag("hiero");
        hideTag("math");
        hideTag("timeline");
        hideTag("chem");
        hideTag("score");
        hideTag("categorytree");
        hideTag("inputbox");
        hideTag("mapframe");
        hideTag("maplink");

        var i;
        for (i in window.wfPluginsT) {
          if (window.wfPluginsT.hasOwnProperty(i)) {
            window.wfPluginsT[i](txt, r);
          }
        }

        hideTemplates(); // templates

        r(
          /(\| *(?:pp?|S|s|с|c|старонкі\d?|pages\d?|seite\d?|alleseiten|лісты\d?|том|volume|band|выпуск|issue|heft|нумар|слупкі\d?|columns\d?|kolonnen\d?|серыя год) *= *)(\d+)[\u00A0 ]?(?:-{1,3}|—) ?(\d+)/g,
          "$1$2—$3",
        );
        r(/(\| *год *= *)(\d{4})[\u00A0 ]?(?:-{1,3}|—) ?(\d{4})/g, "$1$2—$3");

        hide(/^[ \t].*/gm); //lines starting with space
        hide(/(https?|ftp|news|nntp|telnet|irc|gopher):\/\/[^\s\[\]<>"]+ ?/gi); //links
        hide(/^#(redirect|перанакіраванне)/i);
        hideTag("gallery");

        r(/ +(\n|\r)/g, "$1"); // spaces at EOL
        txt = "\n" + txt + "\n";

        // LINKS
        r(/(\[\[:?)(?:category|катэгорыя|к):( *)/gi, "$1Катэгорыя:");
        r(/(\[\[:?)(?:module|модуль):( *)/gi, "$1Модуль:");
        r(/(\[\[:?)(?:template|шаблон|ш):( *)/gi, "$1Шаблон:");
        r(/(\[\[:?)(?:image|выява|file|файл):( *)/gi, "$1Файл:");
        //Linked years, centuries and ranges
        r(
          /(\(|\s)(\[\[[12]?\d{3}\]\])[\u00A0 ]?(-{1,3}|–|—) ?(\[\[[12]?\d{3}\]\])(\W)/g,
          "$1$2—$4$5",
        );
        r(/(\[\[[12]?\d{3}\]\]) ?(гг?\.)/g, "$1" + u + "$2");
        r(
          /(\(|\s)(\[\[[IVX]{1,5}\]\])[\u00A0 ]?(-{1,3}|–|—) ?(\[\[[IVX]{1,5}\]\])(\W)/g,
          "$1$2—$4$5",
        );
        r(/(\[\[[IVX]{1,5}\]\]) ?(стст?\.)/g, "$1" + u + "$2");
        // Nice links
        r(/(\[\[[^|[\]]*)[\u00AD\u200E\u200F]+([^\[\]]*\]\])/g, "$1$2"); // Soft Hyphen & DirMark
        r(
          /\[\[ *([^|[\]]+?) *\| *('''''|'''|'')([^'|[\]]*)\2 *]]/g,
          "$2[[$1|$3]]$2",
        ); // move fomatting out of link text
        r(/\[\[ *([^|[\]]+?) *\| *«([^»|[\]]*)» *\]\]/g, "«[[$1|$2]]»"); // move quotation marks out of link text
        r(/\[\[ *([^|[\]]+?) *\| *„([^“|[\]]*)“ *\]\]/g, "„[[$1|$2]]“");
        r(/\[\[ *([^|[\]]+?) *\| *"([^"|[\]]*)" *\]\]/g, '"[[$1|$2]]"');
        r(/\[\[([^|[\]\n]+)\|([^|[\]\n]+)\]\]/g, processLink); // link shortening
        r(/\[\[ *([^|[\]]+)([^|\[\]()]+?) *\| *\1 *\]\]\2/g, "[[$1$2]]"); // text repetition after link
        r(
          /\[\[ *(?!Файл:|Катэгорыя:)([a-zA-Zа-яёўіА-ЯЁЎІ\u00A0-\u00FF %!\"$&'()*,\-—.\/0-9:;=?\\@\^_`’~]+) *\| *([^|[\]]+) *\]\]([a-zа-яёўі]+)/g,
          "[[$1|$2$3]]",
        ); // "
        hide(/\[\[[^\]|]+/g); // only link part

        //TAGS
        r(/<<(\S.+\S)>>/g, '"$1"'); //<< >>
        r(/(sup>|sub>|\s)-(\d)/g, "$1−$2"); //minus
        r(/(<sup>2<\/sup>|&sup2;)/gi, "²");
        r(/(<sup>3<\/sup>|&sup3;)/gi, "³");
        r(/<(b|strong)>(.*?)<\/(b|strong)>/gi, "'''$2'''");
        r(/<(i|em)>(.*?)<\/(i|em)>/gi, "''$2''");
        r(/^<hr ?\/?>/gim, "----");
        r(/<\/?(hr|br)( [^\/>]+?)? ?\/?>/gi, "<$1$2 />");
        r(
          /(\n== *[a-zа-яёўі\s\.:]+ *==\n+)<references *\/>/gi,
          "$1{\{заўвагі}}",
        );
        hide(/<[a-z][^>]*?>/gi);

        hide(/^(\{\||\|\-).*/gm); // table/row def
        hide(/(^\||^!|!!|\|\|) *[a-z]+=[^|]+\|(?!\|)/gim); // cell style
        hide(/\| +/g); // formatted cell

        r(/[ \t\u00A0]{2,}/g, " "); // double spaces

        // Headings
        r(/^(=+)[ \t\f\v]*(.*?)[ \t\f\v]*=+$/gm, "$1 $2 $1"); //add spaces inside
        r(/([^\r\n])(\r?\n==.*==\r?\n)/g, "$1\n$2"); //add empty line before
        r(/^== гл(\.?|ядзі|ядзіце) ?таксама ==$/gim, "== Гл. таксама ==");
        r(/^== Вонкавыя\sспасылкі ==$/gim, "== Спасылкі ==");
        r(/^== вонкавыя\sспасылкі ==$/gim, "== Спасылкі ==");
        r(/^== У\sСеціве ==$/gim, "== Спасылкі ==");
        r(/^== (.+)[.:] ==$/gm, "== $1 ==");

        r(/–/g, "-");
        r(/«|»|“|”|„/g, '"'); //temp

        // Hyphens and en dashes to pretty dashes
        r(/–/g, "-"); // &ndash; -> hyphen
        r(/(\s)-{1,3} /g, "$1— "); // hyphen -> &mdash;
        r(/(\d)--(\d)/g, "$1—$2"); // -> &mdash;
        r(/(\s)-(\d)/g, "$1−$2"); // hyphen -> minus

        // Entities etc. → Unicode chars
        //r(/&#x([0-9a-f]{1,4});/gi, function(n,a){return String.fromCharCode(eval('0x'+a.substr(-4)))})  //&#x301;
        r(/&copy;/gi, "©");
        r(/&reg;/gi, "®");
        r(/&sect;/gi, "§");
        r(/&euro;/gi, "€");
        r(/&yen;/gi, "¥");
        r(/&pound;/gi, "£");
        r(/&deg;/g, "°");
        r(/\(tm\)|&trade;/gi, "™");
        r(/\.\.\.|&hellip;/g, "…");
        r(/\+-(?!\+|-)|&plusmn;/g, "±");
        r(/~=/g, "≈");
        r(/\^2(\D)/g, "²$1");
        r(/\^3(\D)/g, "³$1");
        r(/&((la|ra|bd|ld)quo|quot);/g, '"');
        r(/([\wа-яА-ЯёЁўЎіІ])'([\wа-яА-ЯёЁўЎіІ])/g, "$1’$2"); // '→’
        r(/([\wа-яА-ЯёЁўЎіІ])ʼ([\wа-яА-ЯёЁўЎіІ])/g, "$1’$2"); // ʼ→’ (U+02BC → U+2019)

        r(/№№/g, "№");

        // Year and century ranges
        r(
          /(\(|\s)([12]?\d{3})[\u00A0 ]?(-{1,3}|—) ?([12]?\d{3})(?![\w-])/g,
          "$1$2—$4",
        );
        r(/([12]?\d{3}) ?(гг?\.)/g, "$1" + u + "$2");
        r(
          /(\(|\s)([IVX]{1,5})[\u00A0 ]?(-{1,3}|—) ?([IVX]{1,5})(?![\w-])/g,
          "$1$2—$4",
        );
        r(/([IVX]{1,5}) ?(стст?\.)/g, "$1" + u + "$2");

        // Reductions
        r(
          /(\d)[\u00A0 ]?(млн|млрд|трлн|(?:м|с|д|к)?м|[км]г)\.?(?=[,;.]| "?[а-яёўі-])/g,
          "$1" + u + "$2",
        );
        r(/(\d)[\u00A0 ](тыс)([^\.А-Яа-яЁёЎўІі])/g, "$1" + u + "$2.$3");
        r(/ISBN:\s?(?=[\d\-]{8,17})/, "ISBN ");

        // Insert/delete spaces
        r(/^([#*:]+)[ \t\f\v]*(?!\{\|)([^ \t\f\v*#:;])/gm, "$1 $2"); //space after #*: unless before table
        r(/(\S) (-{1,3}|—) (\S)/g, "$1" + u + "— $3");
        r(
          /([А-ЯЁЎІ]\.) ?([А-ЯЁЎІ]\.) ?([А-ЯЁЎІ][а-яёўі])/g,
          "$1" + u + "$2" + u + "$3",
        );
        r(/([А-ЯЁЎІ]\.)([А-ЯЁЎІ]\.)/g, "$1 $2");
        r(/([а-яёўі]\.)([А-ЯA-ZЁЎІ])/g, "$1 $2"); // word. word
        r(/([)"а-яa-zёўі\]])\s*,([\[("а-яa-zёўі])/g, "$1, $2"); // word, word
        r(/([)"а-яa-zёўі\]])\s([,;])\s([\[("а-яa-zёўі])/g, "$1$2 $3");
        r(
          /([^%\/\w]\d+?(?:[.,]\d+?)?) ?([%‰])(?!-[А-Яа-яЁёЎўІі])/g,
          "$1" + u + "$2",
        ); //5 %
        r(/(\d) ([%‰])(?=-[А-Яа-яЁёЎўІі])/g, "$1$2"); //5%-й
        r(/([№§])(\s*)(\d)/g, "$1" + u + "$3");
        r(/\( +/g, "(");
        r(/ +\)/g, ")"); //inside ()

        //Temperature
        r(
          /([\s\d=≈≠≤≥<>—("'|])([+±−-]?\d+?(?:[.,]\d+?)?)(([ °^*]| [°^*])[CС])(?=[\s"').,;!?|])/gm,
          "$1$2" + u + "°C",
        ); //'
        r(
          /([\s\d=≈≠≤≥<>—("'|])([+±−-]?\d+?(?:[.,]\d+?)?)(([ °^*]| [°^*])F)(?=[\s"').,;|!?])/gm,
          "$1$2" + u + "°F",
        ); //'

        //Dot → comma in numbers
        r(/(\s\d+)\.(\d+[\u00A0 ]*[%‰°])/gi, "$1,$2");

        // Plugins
        for (i in window.wfPlugins) {
          if (window.wfPlugins.hasOwnProperty(i)) {
            window.wfPlugins[i](txt, r);
          }
        }

        //"" → «»
        for (var j = 1; j <= 2; j++) {
          r(
            /([\xa0\s\x02!|#'"\/(;+-])"([^"]*)([^\s"(|])"([^a-zA-Zа-яА-ЯёіўЁІ0-9])/g,
            "$1«$2$3»$4",
          ); //"
        }
        while (/«[^»]*«/.test(txt)) {
          r(/«([^»]*)«([^»]*)»/g, "«$1„$2“");
        }

        function unhide(s, num) {
          return hidden[num - 1];
        }
        while (txt.match(/\x01\d+\x02/)) {
          r(/\x01(\d+)\x02/g, unhide);
        }
        txt = txt.substr(1, txt.length - 2); // compensation for "txt = '\n' + txt + '\n';"
      }
      function processAllText() {
        txt = $input ? $input.textSelection("getContents") : text;
        processText();
        if ($input) {
          r(/^[\n\r]+/, "");

          $input.textSelection("setContents", txt);
          if (caretPosition) {
            $input.textSelection("setSelection", {
              start:
                caretPosition[0] > txt.length ? txt.length : caretPosition[0],
            });
          }
        } else {
          text = txt;
        }
        if (
          window.auto_comment &&
          window.insertSummary &&
          !document.editform.wpSection.value
        ) {
          window.insertSummary(strings.summary);
        }
      }

      // MAIN CODE

      // Check what's in the first parameter
      var text;
      var isInput;
      var $input;
      if (typeof input === "string") {
        text = input;
      } else {
        isInput =
          input &&
          ((input.nodeType && input.value !== undefined) || // node
            (input.prop && input.prop("nodeType"))); // jQuery object
        $input = $(isInput ? input : "#wpTextbox1");
      }

      var txt = "";
      var hidden = [];
      var winScroll = document.documentElement.scrollTop;
      var caretPosition;
      if ($input) {
        $input.focus();

        caretPosition = $input.textSelection("getCaretPosition", {
          startAndEnd: true,
        });
        if (caretPosition) {
          var $CodeMirrorVscrollbar = $(".CodeMirror-vscrollbar");
          var textScroll = (
            $CodeMirrorVscrollbar.length ? $CodeMirrorVscrollbar : $input
          ).scrollTop();
          if (caretPosition[0] === caretPosition[1]) {
            processAllText();
          } else {
            txt = $input.textSelection("getSelection");
            processText();
            // replaceSelection doesn't work with MediaWiki 1.30 in case this gadget is loaded
            // from other wiki
            $input.textSelection("encapsulateSelection", {
              replace: true,
              peri: txt,
            });
            // In CodeMirror, the selection isn't preserved, so we do it explicitly
            $input.textSelection("setSelection", {
              start: caretPosition[0],
              end: caretPosition[0] + txt.length,
            });
          }
          ($CodeMirrorVscrollbar.length
            ? $CodeMirrorVscrollbar
            : $input
          ).scrollTop(textScroll);
          // If something went wrong
        } else if (confirm(strings.fullText)) {
          processAllText();
        }
      } else {
        processAllText();
        return text;
      }

      // scroll back, for 2017 wikitext editor, IE, Opera
      document.documentElement.scrollTop = winScroll;
    };

    function registerWikificatorTool() {
      registerTool({
        name: "wikificator",
        position: 100,
        title: strings.name,
        label: strings.tooltip,
        callback: Wikify,
        classic: {
          icon: "//upload.wikimedia.org/wikipedia/commons/0/06/Wikify-toolbutton.png",
        },
        visual: {
          icon: "//upload.wikimedia.org/wikipedia/commons/thumb/4/41/Wikificator_VE_icon.svg/20px-Wikificator_VE_icon.svg.png",
          modes: ["source"],
          addRightAway: true,
        },
      });
    }

    registerWikificatorTool();

    $("#editform").on("keydown", function (e) {
      // Ctrl+Alt+W on Windows, Ctrl+Shift+W on Mac
      if (
        e.ctrlKey &&
        !e.metaKey &&
        (clientProfile.platform === "mac"
          ? e.shiftKey && !e.altKey
          : !e.shiftKey && e.altKey) &&
        e.keyCode === 87
      ) {
        Wikify();
      }
    });
  })(),
);
// </nowiki>
