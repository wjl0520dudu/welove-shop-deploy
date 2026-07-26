FROM maven:3.9.9-eclipse-temurin-17 AS build

WORKDIR /workspace
ARG MODULE

# Each Spring service may depend on the shared common modules. Copy only the
# Java build inputs so local AI-service secrets and frontend artifacts never
# enter this image build context.
COPY pom.xml ./
COPY common ./common
COPY gateway ./gateway
COPY services ./services
COPY admin-bff ./admin-bff

RUN mvn -B -ntp -pl "${MODULE}" -am clean package -DskipTests \
    && artifact="$(find "${MODULE}/target" -maxdepth 1 -type f -name '*.jar' ! -name 'original-*' -print -quit)" \
    && test -n "${artifact}" \
    && cp "${artifact}" /tmp/app.jar

FROM eclipse-temurin:17-jre-jammy

WORKDIR /app
COPY --from=build /tmp/app.jar ./app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
