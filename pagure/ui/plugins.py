# -*- coding: utf-8 -*-

"""
 (c) 2014-2017 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>
   Farhaan Bukhsh <farhaan.bukhsh@gmail.com>

"""

# pylint: disable=too-many-branches

import logging

import flask
from sqlalchemy.exc import SQLAlchemyError

import pagure.exceptions
import pagure.lib
import pagure.lib.plugins
import pagure.forms
from pagure.exceptions import FileNotFoundException
from pagure.ui import UI_NS
from pagure.utils import login_required
from pagure.lib.decorators import is_repo_admin


_log = logging.getLogger(__name__)


@UI_NS.route('/<repo>/settings/<plugin>/', methods=('GET', 'POST'))
@UI_NS.route('/<repo>/settings/<plugin>', methods=('GET', 'POST'))
@UI_NS.route('/<namespace>/<repo>/settings/<plugin>/', methods=('GET', 'POST'))
@UI_NS.route('/<namespace>/<repo>/settings/<plugin>', methods=('GET', 'POST'))
@UI_NS.route(
    '/<repo>/settings/<plugin>/<int:full>/',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/<repo>/settings/<plugin>/<int:full>',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/<namespace>/<repo>/settings/<plugin>/<int:full>/',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/<namespace>/<repo>/settings/<plugin>/<int:full>',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<repo>/settings/<plugin>/',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<namespace>/<repo>/settings/<plugin>/',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<repo>/settings/<plugin>',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<namespace>/<repo>/settings/<plugin>',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<repo>/settings/<plugin>/<int:full>/',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<namespace>/<repo>/settings/<plugin>/<int:full>/',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<repo>/settings/<plugin>/<int:full>',
    methods=('GET', 'POST'))
@UI_NS.route(
    '/fork/<username>/<namespace>/<repo>/settings/<plugin>/<int:full>',
    methods=('GET', 'POST'))
@login_required
@is_repo_admin
def view_plugin(repo, plugin, username=None, namespace=None, full=True):
    """ Presents the settings of the project.
    """
    repo = flask.g.repo

    # Private repos are not allowed to leak information outside so disabling CI
    # enables us to keep the repos totally discreate and prevents from leaking
    # information outside
    if repo.private and plugin == 'Pagure CI':
        flask.abort(404, 'Plugin disabled')

    if plugin in pagure.config.config.get('DISABLED_PLUGINS', []):
        flask.abort(404, 'Plugin disabled')

    if plugin == 'default':
        flask.abort(403, 'This plugin cannot be changed')

    plugin = pagure.lib.plugins.get_plugin(plugin)
    fields = []
    new = True
    dbobj = plugin.db_object()

    if hasattr(repo, plugin.backref):
        dbobj = getattr(repo, plugin.backref)

        # There should always be only one, but let's double check
        if dbobj:
            new = False
        else:
            dbobj = plugin.db_object()

    form = plugin.form(obj=dbobj)
    for field in plugin.form_fields:
        fields.append(getattr(form, field))

    if form.validate_on_submit():
        form.populate_obj(obj=dbobj)

        if new:
            dbobj.project_id = repo.id
            flask.g.session.add(dbobj)
        try:
            flask.g.session.flush()
        except SQLAlchemyError as err:  # pragma: no cover
            flask.g.session.rollback()
            _log.exception('Could not add plugin %s', plugin.name)
            flask.flash(
                'Could not add plugin %s, please contact an admin'
                % plugin.name)

            return flask.render_template(
                'plugin.html',
                select='settings',
                full=full,
                repo=repo,
                username=username,
                namespace=namespace,
                plugin=plugin,
                form=form,
                fields=fields)

        if form.active.data:
            # Set up the main script if necessary
            plugin.set_up(repo)
            # Install the plugin itself
            try:
                plugin.install(repo, dbobj)
                flask.flash('Hook %s activated' % plugin.name)
            except FileNotFoundException as err:
                _log.exception(err)
                flask.abort(404, 'No git repo found')
        else:
            try:
                plugin.remove(repo)
                flask.flash('Hook %s deactivated' % plugin.name)
            except FileNotFoundException as err:
                _log.exception(err)
                flask.abort(404, 'No git repo found')

        flask.g.session.commit()

        return flask.redirect(flask.url_for(
            'ui_ns.view_settings', repo=repo.name, username=username,
            namespace=namespace))

    return flask.render_template(
        'plugin.html',
        select='settings',
        full=full,
        repo=repo,
        namespace=namespace,
        username=username,
        plugin=plugin,
        form=form,
        fields=fields)
