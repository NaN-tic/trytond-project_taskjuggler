# This file is part of project_taskjuggler module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelSQL, ModelView
from trytond.pool import PoolMeta, Pool
import os
import logging
from tempfile import NamedTemporaryFile
import codecs
import subprocess

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    logging.getLogger('project_taskjuggler').error(
        'Unable to import jinja2. Install jinja2 package.')


__metaclass__ = PoolMeta
__all__ = ['TaskJuggler', 'Work', 'EmployeeTrackers', 'Employee',
        'TaskJugglerProjectWork']


def command(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    output, err = process.communicate()
    return output, err


# class ProjectTracker:
#     __name__ = 'project.work.tracker'

#     employees = fields.Many2Many('project.tracker-company.employee',
#         'employee', 'tracker', 'Trackers')


class EmployeeTrackers(ModelSQL):
    'Employee - Trackers'
    __name__ = 'project.tracker-company.employee'
    _table = 'tracker_employee_rel'

    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', select=True)
    tracker = fields.Many2One('project.work.tracker', 'Tracker',
        ondelete='CASCADE', select=True)


class Employee:
    __name__ = 'company.employee'

    trackers = fields.Many2Many('project.tracker-company.employee', 'employee',
        'tracker', 'Trackers')


class Work:
    __name__ = 'project.work'

    resources = fields.Function(fields.Many2Many('company.employee', None,
        None, 'Resources'), 'get_resources')
    taskjuggler_trackers = fields.Function(fields.Many2Many(
        'project.work.tracker', None, None, 'Trackers'),  'get_trackers')
    taskjuggler_tasks = fields.Function(fields.Many2Many(
        'project.work', None, None, 'TaskJuggler Tasks'),
        'get_tasks')
    taskjuggler_code = fields.Function(fields.Char('TaskJuggler Code'),
        'get_taskjuggler_code')

    def get_taskjuggler_code(self, name=None):
        return "task%s.task%st%s.task%s" % (self.parent.code,
            self.parent.code, self.tracker.id, self.code)

    def get_resources(self, name=None):
        Employee = Pool().get('company.employee')
        employees = Employee.search([])
        return [x.id for x in employees if self.tracker in x.trackers]

    def get_trackers(self, name=None):
        trackers = set()
        for task in self.taskjuggler_tasks:
            trackers.add(task.tracker.id)
        return list(trackers)

    def get_dependencies(self):
        if not self.predecessors:
            return []

        dependencies = []
        for task in self.predecessors:
            dependencies.append(task)
            dependencies += task.get_dependencies()
        return dependencies

    def get_tasks(self, name=None):
        tasks = self.search([
            ('parent', '=', self.id),
            ('state', '=', 'opened')])

        dependencies = []
        for task in tasks:
            dependencies += task.get_dependencies()

        return list(set([task.id for task in tasks+dependencies]))


class TaskJugglerProjectWork(ModelSQL):
    'TaskJuggler - Project Work'
    __name__ = 'taskjuggler.project-project.work'
    _table = 'taskjuggler_project_rel'

    taskjuggler = fields.Many2One('taskjuggler.project', 'TaskJuggler',
        ondelete='CASCADE', select=True)
    project = fields.Many2One('project.work', 'Project',
        ondelete='CASCADE', select=True)


class TaskJuggler(ModelSQL, ModelView):
    "TaskJuggler"
    __name__ = 'taskjuggler.project'

    name = fields.Char('Name', required=True)
    start_date = fields.Date("Start", required=True)
    duration = fields.Char("Duration", required=True)
    url = fields.Char('Url')
    output = fields.Char('Output Directory')
    project_ids = fields.Function(fields.Char("Ids"), 'get_project_ids')
    projects = fields.Many2Many('taskjuggler.project-project.work',
         'taskjuggler', 'project', 'Projects',
         domain=[('type', '=', 'project')], depends=['type'])

    @classmethod
    def __setup__(cls):
        super(TaskJuggler, cls).__setup__()
        cls._buttons.update({
            'export': {}
            })
        cls._error_messages.update({
                'taskjuggler_result': ('TaskJuggler Compilation Result %s:\n '
                    '%s'),
                })

    def get_project_ids(self, name=None):
        ids = []
        for project in self.projects:
            ids.append('p%s' % project.id)
        return ",".join(ids)

    @classmethod
    @ModelView.button
    def export(cls, projects):
        pool = Pool()
        Employee = pool.get('company.employee')

        for project in projects:
            template_dir = os.path.join(os.path.dirname(__file__), 'template')
            template_loader = FileSystemLoader(searchpath=template_dir)
            template_env = Environment(loader=template_loader)

            #export project
            project_template = template_env.get_template('project.jinja')
            project_tjp = project_template.render(project=project)

            employees = Employee.search([])
            employee_template = template_env.get_template('resource.jinja')
            employee_tjp = employee_template.render(employees=employees)

            line_template = template_env.get_template('project_line.jinja')
            line_tjp = line_template.render(lines=project.projects)

            report_template = template_env.get_template('reports.jinja')
            report_tjp = report_template.render(lines=project.projects)

            tjpf = NamedTemporaryFile(suffix=".tjp", delete=False)
            tjpfc = codecs.open(tjpf.name, "w", "utf-8")
            tjpfc.write(project_tjp)
            tjpfc.write(employee_tjp)
            tjpfc.write(line_tjp)
            tjpfc.write(report_tjp)
            tjpfc.close()

            cmd = ['tj3', '--output-dir', project.output,  tjpf.name]
            r, a = command(cmd)
            cls.raise_user_error('taskjuggler_result', (r, a))




















