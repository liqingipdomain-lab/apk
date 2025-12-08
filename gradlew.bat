@echo off
:: Copyright 2015 the original authors.
:: Licensed under the Apache License, Version 2.0

set DEFAULT_JVM_OPTS=

set DIR=%~dp0
set APP_HOME=%DIR%
set CLASSPATH=%APP_HOME%\gradle\wrapper\gradle-wrapper.jar

if not defined JAVA_HOME goto findJava
set JAVA_EXE=%JAVA_HOME%\bin\java.exe
if exist "%JAVA_EXE%" goto init

:findJava
set JAVA_EXE=java.exe

:init
"%JAVA_EXE%" %DEFAULT_JVM_OPTS% -Dorg.gradle.appname=gradlew -classpath "%CLASSPATH%" org.gradle.wrapper.GradleWrapperMain %*
exit /b %ERRORLEVEL%
