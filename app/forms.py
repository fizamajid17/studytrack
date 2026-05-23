from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Create account')

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
            raise ValidationError('Email already registered.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')

class SubjectForm(FlaskForm):
    name = StringField('Subject name', validators=[DataRequired(), Length(max=100)])
    color = SelectField('Color', choices=[
        ('blue', 'Blue'), ('green', 'Green'), ('purple', 'Purple'),
        ('orange', 'Orange'), ('red', 'Red'), ('teal', 'Teal')
    ])
    submit = SubmitField('Add subject')

class NoteForm(FlaskForm):
    content = TextAreaField('Your notes', validators=[DataRequired()])
    submit = SubmitField('Save notes')