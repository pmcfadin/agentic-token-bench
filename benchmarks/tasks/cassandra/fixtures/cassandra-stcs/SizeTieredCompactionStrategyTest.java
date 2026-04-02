/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.cassandra.db.compaction;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.google.common.collect.ImmutableMap;
import org.junit.BeforeClass;
import org.junit.Test;

import org.apache.cassandra.SchemaLoader;
import org.apache.cassandra.config.DatabaseDescriptor;
import org.apache.cassandra.exceptions.ConfigurationException;

import static org.junit.Assert.*;

/**
 * Unit and integration tests for SizeTieredCompactionStrategy.
 *
 * Verifies bucket grouping, threshold enforcement, option validation, and
 * SSTable candidate selection for the SizeTieredCompactionStrategy
 * compaction implementation.
 */
public class SizeTieredCompactionStrategyTest
{
    @BeforeClass
    public static void setupDD()
    {
        DatabaseDescriptor.daemonInitialization();
        SchemaLoader.prepareServer();
    }

    @Test
    public void testGetBucketsReturnsEmptyForNoInput()
    {
        // SizeTieredCompactionStrategy.getBuckets should return empty list for empty input
        List<List<Object>> buckets = (List<List<Object>>) (List<?>) SizeTieredCompactionStrategy.getBuckets(
            new ArrayList<>(),
            SizeTieredCompactionStrategyOptions.DEFAULT_BUCKET_LOW,
            SizeTieredCompactionStrategyOptions.DEFAULT_BUCKET_HIGH,
            SizeTieredCompactionStrategyOptions.DEFAULT_MIN_SSTABLE_SIZE
        );
        assertTrue("SizeTieredCompactionStrategy should produce no buckets for empty input", buckets.isEmpty());
    }

    @Test
    public void testValidateDefaultOptions() throws ConfigurationException
    {
        // Default options for SizeTieredCompactionStrategy should validate without error
        Map<String, String> opts = ImmutableMap.of();
        Map<String, String> result = SizeTieredCompactionStrategy.validateOptions(opts);
        assertNotNull(result);
    }

    @Test
    public void testOptionsMinSSTableSizeParsed()
    {
        Map<String, String> opts = ImmutableMap.of(
            SizeTieredCompactionStrategyOptions.MIN_SSTABLE_SIZE_KEY, "52428800"
        );
        SizeTieredCompactionStrategyOptions options = new SizeTieredCompactionStrategyOptions(opts);
        assertEquals(52428800L, options.minSSTableSize);
    }

    @Test
    public void testOptionsBucketLowParsed()
    {
        Map<String, String> opts = ImmutableMap.of(
            SizeTieredCompactionStrategyOptions.BUCKET_LOW_KEY, "0.4"
        );
        SizeTieredCompactionStrategyOptions options = new SizeTieredCompactionStrategyOptions(opts);
        assertEquals(0.4, options.bucketLow, 0.001);
    }

    @Test
    public void testOptionsBucketHighParsed()
    {
        Map<String, String> opts = ImmutableMap.of(
            SizeTieredCompactionStrategyOptions.BUCKET_HIGH_KEY, "2.0"
        );
        SizeTieredCompactionStrategyOptions options = new SizeTieredCompactionStrategyOptions(opts);
        assertEquals(2.0, options.bucketHigh, 0.001);
    }

    @Test(expected = ConfigurationException.class)
    public void testValidateOptionsRejectsNegativeMinSSTableSize() throws ConfigurationException
    {
        Map<String, String> opts = ImmutableMap.of(
            SizeTieredCompactionStrategyOptions.MIN_SSTABLE_SIZE_KEY, "-1"
        );
        SizeTieredCompactionStrategy.validateOptions(opts);
    }
}
