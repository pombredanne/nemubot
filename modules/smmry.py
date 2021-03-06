"""Summarize texts"""

# PYTHON STUFFS #######################################################

from urllib.parse import quote

from nemubot import context
from nemubot.exception import IMException
from nemubot.hooks import hook
from nemubot.tools import web

from nemubot.module.more import Response
from nemubot.module.urlreducer import LAST_URLS


# GLOBALS #############################################################

URL_API = "https://api.smmry.com/?SM_API_KEY=%s"


# LOADING #############################################################

def load(context):
    if not context.config or "apikey" not in context.config:
        raise ImportError("You need a Smmry API key in order to use this "
                          "module. Add it to the module configuration file:\n"
                          "<module name=\"smmry\" apikey=\"XXXXXXXXXXXXXXXX\" "
                          "/>\nRegister at https://smmry.com/partner")
    global URL_API
    URL_API = URL_API % context.config["apikey"]


# MODULE INTERFACE ####################################################

@hook.command("smmry",
              help="Summarize the following words/command return",
              help_usage={
                  "WORDS/CMD": ""
              },
              keywords={
                  "keywords?=X": "Returns keywords instead of summary (count optional)",
                  "length=7": "The number of sentences returned, default 7",
                  "break": "inserts the string [BREAK] between sentences",
                  "ignore_length": "returns summary regardless of quality or length",
                  "quote_avoid": "sentences with quotations will be excluded",
                  "question_avoid": "sentences with question will be excluded",
                  "exclamation_avoid": "sentences with exclamation marks will be excluded",
              })
def cmd_smmry(msg):
    if not len(msg.args):
        global LAST_URLS
        if msg.channel in LAST_URLS and len(LAST_URLS[msg.channel]) > 0:
            msg.args.append(LAST_URLS[msg.channel].pop())
        else:
            raise IMException("I have no more URL to sum up.")

    URL = URL_API
    if "length" in msg.kwargs:
        if int(msg.kwargs["length"]) > 0 :
            URL += "&SM_LENGTH=" + msg.kwargs["length"]
        else:
            msg.kwargs["ignore_length"] = True
    if "break" in msg.kwargs: URL += "&SM_WITH_BREAK"
    if "ignore_length" in msg.kwargs: URL += "&SM_IGNORE_LENGTH"
    if "quote_avoid" in msg.kwargs: URL += "&SM_QUOTE_AVOID"
    if "question_avoid" in msg.kwargs: URL += "&SM_QUESTION_AVOID"
    if "exclamation_avoid" in msg.kwargs: URL += "&SM_EXCLAMATION_AVOID"
    if "keywords" in msg.kwargs and msg.kwargs["keywords"] is not None and int(msg.kwargs["keywords"]) > 0: URL += "&SM_KEYWORD_COUNT=" + msg.kwargs["keywords"]

    res = Response(channel=msg.channel)

    if web.isURL(" ".join(msg.args)):
        smmry = web.getJSON(URL + "&SM_URL=" + quote(" ".join(msg.args)), timeout=23)
    else:
        cnt = ""
        for r in context.subtreat(context.subparse(msg, " ".join(msg.args))):
            if isinstance(r, Response):
                for i in range(len(r.messages) - 1, -1, -1):
                    if isinstance(r.messages[i], list):
                        for j in range(len(r.messages[i]) - 1, -1, -1):
                            cnt += r.messages[i][j] + "\n"
                    elif isinstance(r.messages[i], str):
                        cnt += r.messages[i] + "\n"
                    else:
                        cnt += str(r.messages) + "\n"

            elif isinstance(r, Text):
                cnt += r.message + "\n"

            else:
                cnt += str(r) + "\n"

        smmry = web.getJSON(URL, body="sm_api_input=" + quote(cnt), timeout=23)

    if "sm_api_error" in smmry:
        if smmry["sm_api_error"] == 0:
            title = "Internal server problem (not your fault)"
        elif smmry["sm_api_error"] == 1:
            title = "Incorrect submission variables"
        elif smmry["sm_api_error"] == 2:
            title = "Intentional restriction (low credits?)"
        elif smmry["sm_api_error"] == 3:
            title = "Summarization error"
        else:
            title = "Unknown error"
        raise IMException(title + ": " + smmry['sm_api_message'].lower())

    if "keywords" in msg.kwargs:
        smmry["sm_api_content"] = ", ".join(smmry["sm_api_keyword_array"])

    if "sm_api_title" in smmry and smmry["sm_api_title"] != "":
        res.append_message(smmry["sm_api_content"], title=smmry["sm_api_title"])
    else:
        res.append_message(smmry["sm_api_content"])

    return res
