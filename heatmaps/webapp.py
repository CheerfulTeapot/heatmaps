#!/usr/bin/env python3
"""
    The web implementation for the heatmaps service
    will probably also put the order service here
"""

# TODO do we need prov for generating lists of terms from the ontology?

# TODO: need to clear heatmap id and add a message on download!
# need to add a "collecting data" message for large queries
# need to add datetime and heatmap prov id to the csv download
# need to make the title of the csv nice
# neet to develop a series of tests designed to wreck the text input box

from os import environ
from flask import Flask, url_for, request, render_template, render_template_string, make_response, abort

if environ.get('HEATMAP_PROD',None):
    embed = lambda args: print("THIS IS PRODUCTION AND PRODUCTION DOESNT LIKE IPYTHON ;_;")
else:
    from IPython import embed  #FIXME

from .services import heatmap_service, summary_service, term_service

###
#   Templates (FIXME extract)
###

class Templated:
    TEMPLATE = ""
    def __init__(self, render_kwargs, render_call=render_template_string):
        self.render_kwargs = render_kwargs
        self.render_call = render_call

    def render(self):
        return self.render_call(self.TEMPLATE, **self.render_kwargs)

class FormField:
    def __init__(self, title, type_, callback):
        self.title = title
        self.type = type_
        self.name = title.lower().replace(' ','_')  #FIXME
        self._callback = callback

    def callback(self):
        return self._callback(self.name)

    @staticmethod
    def factory(titles, types, callbacks):
        """ form field factory """
        return [FormField(title, type_, callback) for title, type_, callback in zip(titles, types, callbacks)]

    def __repr__(self):
        return "<FormField %s %s>" % (str(self.type), str(self.title)) 

class Form(Templated):  # FIXME separate callbacks? nah?

    TEMPLATE = """
    <!doctype html>
    <title>{{title}}</title>
    <form action=terms/submit method=POST enctype=multipart/form-data>
        {% for field in fields %}
            {{field.title}}: <br>
            <input type={{field.type}} name={{field.name}}> <br>
        {% endfor %}
        <input type=submit value=Submit>
    </form>
    """

    def __init__(self, title, titles, types, callbacks, exit_on_success=True):
        self.title = title
        self.fields = FormField.factory(titles, types, callbacks)
        render_kwargs = dict(title=self.title, fields=self.fields)#, action_url=action_url)
        super().__init__(render_kwargs)
        self.exit_on_success = exit_on_success  # single field forms mutex

    def data_received(self):
        if self.exit_on_success:
            print('dr', self.fields)
            for field in self.fields:
                out = field.callback()
                print(field, 'data_received', out)
                if out:
                    if type(out) == str:  #FIXME all callbacks need to return a response object or nothing
                        return 'Your submisison is processing, your number is # \n' + out
                        return self.render() + "<br>" + out  # rerender the original form but add the output of the callback
                    else:
                        return out
                    #return "Did this work?"
            return "You didnt submit anything... go back and try again!"
            return self.render()  # so that we don't accidentally return None
        else:
            for field in self.fields:
                field.callback()
                return "WUT"


hmserv = heatmap_service(summary_service(), term_service())  # mmm nasty singletons

hmapp = Flask("heatmap service")


#base_ext = "/servicesv1/v1/heatmaps/"
#hmext = base_ext + "heatmap/"

ext_path = "/servicesv1/v1/heatmaps"



def HMID(name):
    #validate doi consider the alternative to not present the doi directly via our web interface?
    try:
        hm_id = int(request.form[name])
    except ValueError:  # FIXME error handling should NOT be written in here?
        return None
    except:
        raise
    return csv_from_id(hm_id)

def TERMLIST(name):  # TODO fuzz me!  FIXME "!" causes the summary service to crash!
    # identify separator  # this is hard, go with commas I think we must
    # split
    # pass into make_heatmap_data
    # return csv and id
    data = request.form[name]
    if not data:  # term list is empty
        return None
    terms = [t.strip().rstrip() for t in data.split(',')]  # FIXME chemical names :/
    return do_terms(terms)

def TERMFILE(name):  # TODO fuzz me!  #FIXME blank lines cause 500 errors!
    # identify sep
    # split
    # pass into make_heatmap_data
    # return csv and id
    try:
        file = request.files[name]
        print('TERMFILE type', file)
        terms = [l.rstrip().decode() for l in file.stream.readlines() if l]
        return do_terms(terms)
    except KeyError:
        raise

def do_terms(terms):
    # FIXME FIXME this is NOT were we should be doing data sanitizaiton :/
    if not terms:
        print('no terms!')
        return None
    hm_data, hp_id, timestamp = hmserv.make_heatmap_data(*terms)
    if hp_id == None:  # no id means we'll give the data but not store it (for now :/)
        return repr((timestamp, hm_data))  # FIXME this is a nasty hack to pass error msg out
    #return repr((hm_data, hp_id, timestamp))
    base_url = 'http://' + request.host + ext_path
    output = """
            <!doctype html>
            <title>Submit</title>
            When your job is finished your heatmap can be downloaded as a png, a csv or as a json file at:
            <br><br>
            <a href={url}.csv>{url}.csv</a>
            <br>
            <a href={url}.json>{url}.json</a>
            <br>
            <a href={url}.png>{url}.png</a>
            <br><br>
            If you ever need to download your heatmap again you can get it again
            as long as you know your heatmap id which is {id}.
            """.format(url=base_url + '/prov/' + str(hp_id), id=hp_id)
    return output


def data_from_id(hm_id, filetype):
    hm_id = int(hm_id)
    collTerms = None
    if filetype == 'png':
        collSources = 'collapse views to sources'
    else:
        collSources = None

    sortTerms = 'literature'
    sortTerms = 'frequency'
    sortSources = 'identifier'
    sortSources = 'frequency'
    idSortTerms = None  # note: should be a SOURCE identifier
    idSortSources = 'Sleep'
    idSortSources = None  # note: should be a TERM identifier
    ascTerms = False
    ascSources = True
    data, filename, mimetype = hmserv.output(hm_id, filetype, sortTerms, sortSources, collTerms, collSources, idSortTerms, idSortSources, ascTerms, ascSources)
    if data:
        if filetype == 'csv':
            attachment = 'attachment; '
        else:
            attachment = ''
        response = make_response(data)
        response.headers['Content-Disposition'] = '%sfilename = %s' % (attachment, filename)
        response.mimetype = mimetype
        return response
    else:
        return abort(404)


terms_form = Form("NIF heatmaps from terms",
                    ("Heatmap ID (int)","Term list (comma separated)", "Term file (newline separated)"),  #TODO select!
                    ('text','text','file'),
                    (HMID, TERMLIST, TERMFILE))

@hmapp.route(ext_path + "/explore/<hm_id>", methods = ['GET'])
def hm_explore(hm_id):
    hm_id = int(hm_id)
    timestamp = hmserv.get_timestamp_from_id(hm_id)
    if not timestamp:
        return abort(404)
    else:
        date, time = timestamp.split('T')
    heatmap_data = hmserv.get_heatmap_data_from_id(hm_id)

    sorting_ops = '<br>'.join(hmserv.supported_termSort)
    term_ids = '<br>'.join(sorted(heatmap_data))
    tuples = [[v if v is not None else '' for v in hmserv.term_server.term_id_expansion(term)]
              for term in heatmap_data]
    cols = [c for c in zip(*tuples)]
    justs = [max([len(s) for s in col]) + 1 for col in cols]
    cols2 = []
    for i, just in enumerate(justs):
        cols2.append([s.ljust(just) for s in cols[i]])

    titles = ''.join([s.ljust(just) for s, just
                      in zip(('Input', 'CURIE', 'Label', 'Query'), justs)])

    rows = [titles] + sorted([''.join(r) for r in zip(*cols2)])
    expansion = '<pre>' + '\n'.join(rows) + '</pre>'

    page = """<!doctype html>
<title>NIF Heatmap {hm_id} exploration</title>
<h1>Explore heatmap {hm_id}</h1>
<h2>Created on: {date} at {time}</h2>
<h3>Sorting Options:</h3>
{sorting_ops}
<h3>Terms:</h3>
{term_ids}<br>
<h3>Expansion: putative term, curie, label, query</h3>
{expansion}""".format(hm_id=hm_id, date=date, time=time, term_ids=term_ids,
               sorting_ops=sorting_ops, expansion=expansion)

    return page

#@hmapp.route(hmext + "terms", methods = ['GET','POST'])
@hmapp.route(ext_path + "/terms", methods = ['GET'])
def hm_terms():
    #if request.method == 'POST':
        #return terms_form.data_received()
    #else:
    return terms_form.render()

@hmapp.route(ext_path + "/terms/submit", methods = ['GET', 'POST'])
def hm_submit():
    if request.method == 'POST':
        # TODO need WAY more here
        # specifically we need to return a "job submitted" page
        # that will have js and do a long poll that will update the
        # page to tell users that their job is done
        # this will require reworking when we put things into the database
        # and possibly the schema :/
        return terms_form.data_received()
    else:
        return "Nothing submited FIXME need to keep session alive??!"
    

@hmapp.route(ext_path + "/prov/<hm_id>", methods = ['GET'])
@hmapp.route(ext_path + "/prov/<hm_id>.<filetype>", methods = ['GET'])
def hm_getfile(hm_id, filetype=None):
    try:
        hm_id = int(hm_id)
        if filetype in hmserv.supported_filetypes:
            return data_from_id(hm_id, filetype)
        else:
            return abort(404)
    except ValueError:
        return abort(404)
        #return 'Invalid heatmap identifier "%s", please enter an integer.' % hm_id, 404
        #return None, 404
    

#@hmapp.route(hmext + )

@hmapp.route(ext_path + '/', methods = ['GET'])
@hmapp.route(ext_path, methods = ['GET'])
def overview():
    base_url = 'http://' + request.host + ext_path
    page = """
    <!doctype html>
    <title>NIF Heatmaps</title>
    <h1>NIF heatmaps services </h1>
    Submit lists of terms and download overviews of the entireity of the NIF data federation.<br>
    Use the form found <a href={terms_url}>here</a> to submit lists of terms or
    you can use the<br>REST api described in the documentation. <br>
    Documentation can be found here: <br>
    <a href={docs_url}>{docs_url}</a>
    """.format(docs_url=base_url + '/docs', terms_url=base_url + '/terms')
    return page

@hmapp.route(ext_path + '/docs', methods = ['GET'])
@hmapp.route(ext_path + '/docs/', methods = ['GET'])
def docs():
    base_url = 'http://' + request.host + ext_path
    page = """
    <!doctype html>
    <title>NIF Heatmaps Documentation</title>
    <h1>NIF heatmaps documentation</h1>
    To view an existing heatmap append the heatmapid to the following url: <br>
    <a href={prov_url}>{prov_url}</a><br>
    Currently supported filetypes are csv, json, and png. <br>
    Example: <a href={prov_url}0.png>{prov_url}0.png</a> (note that this heatmap doesn't actually exist)
    """.format(prov_url=base_url + ext_path + '/prov/')
    return page


###
#   various POST/GET handlers  XXX NOT BEING USED
##



def terms_POST():
    print(request)
    for field in term_fields:
        data = field.get()
        if data:
            if field.type == 'text':
                terms = file_to_terms(data)
            elif field.type == 'file':
                terms = file_to_terms(data)


    term_file = request.files['term_file']
    term_list = request.form['term_list']
    if heatmap_doi:
        return
    elif term_file:
        terms = file_to_terms(term_file)
        return repr(terms)
    elif term_list:
        print(term_list)
        return repr(term_list)
    else:
        return None
    hm_data, fails = hmserv.get_term_counts(*terms)
    ###return repr(hm_data) + "\n\n" + str(fails)
    #return repr(terms)

#@hmapp.route('/')
def terms_GET():
    form = """
    <form method=POST enctype=multipart/form-data action="terms">
        Term list:<br>
        <input type=text name=term_list>
        <br>
        Term file:<br>
        <input type=file name=term_file>
        <br>
        <input type=submit value=Submit>
    </form>
    """
    #url = url_for(hmext + 'terms')  #FIXME
    #return "Paste in a list of terms or select a terms file"
    return form #% url


###
#   Utility funcs that will be moved elsewhere eventually  XXX NOT BEING USED
##

def file_to_terms(file):  # TODO
    # detect the separator
    # split
    # sanitize
    return "brain"

def do_sep(string):
    return string

#please login to get a doi? implementing this with an auth cookie? how do?

def main(port=5000):
    if environ.get('HEATMAP_PROD',None):
        hmapp.debug = False
        hmapp.run(host='0.0.0.0')  # 0.0.0.0 tells flask to listen externally
    else:
        hmapp.debug = True
        hmapp.run(host='127.0.0.1', port=port)


if __name__ == '__main__':
    main()
