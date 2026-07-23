FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /workspace
ARG MODULE
COPY . .
RUN mvn -pl ${MODULE} -am package -DskipTests

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
ARG MODULE
COPY --from=build /workspace/${MODULE}/target/*.jar /app/app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
