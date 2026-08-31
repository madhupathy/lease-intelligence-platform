FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /app

COPY pom.xml ./
RUN mvn -B dependency:go-offline

COPY src ./src
RUN mvn -B package -DskipTests

FROM eclipse-temurin:21-jre

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app app

COPY --from=build /app/target/risk-engine-0.1.0.jar app.jar
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && chown app:app /docker-entrypoint.sh app.jar

USER app

ENV PORT=8081
ENV DB_VALIDATE_MAX_ATTEMPTS=5
ENV DB_VALIDATE_RETRY_DELAY_SEC=30

EXPOSE 8081

ENTRYPOINT ["/docker-entrypoint.sh"]
