#!/usr/bin/env sh

# Copyright 2015 the original authors.
# Licensed under the Apache License, Version 2.0

DEFAULT_JVM_OPTS=""

APP_HOME=$(cd "$(dirname "$0")"; pwd)

CLASSPATH=$APP_HOME/gradle/wrapper/gradle-wrapper.jar

JAVA_EXE=${JAVA_HOME}/bin/java
if [ -x "$JAVA_EXE" ]; then
  JAVACMD="$JAVA_EXE"
else
  JAVACMD=java
fi

exec "$JAVACMD" $DEFAULT_JVM_OPTS -Dorg.gradle.appname=gradlew -classpath "$CLASSPATH" org.gradle.wrapper.GradleWrapperMain "$@"
